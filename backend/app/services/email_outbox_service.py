import asyncio
import logging
import time
from datetime import datetime, timedelta
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import SessionLocal
from app.core.notification_lifecycle import EmailStatus
from app.models.email_outbox import EmailOutbox
from app.services.email_sender import build_email_sender

logger = logging.getLogger(__name__)


def _retry_delays(raw: str) -> list[int]:
    """解析重试延迟配置字符串，返回秒数列表"""
    delays = []
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit() and int(part) > 0:
            delays.append(int(part))
    return delays or [60, 300, 900, 3600, 21600]


def _retry_delay(attempts: int, delays: list[int]) -> int:
    """根据尝试次数和延迟列表，返回当前尝试的延迟秒数"""
    return delays[min(max(attempts - 1, 0), len(delays) - 1)]


def _sanitize_error(exc: Exception, *, to_email: str | None = None) -> str:
    """将异常转换为字符串，替换邮箱地址为[email]，截断为 500 字个字符"""
    text = f"{type(exc).__name__}: {exc}"
    if to_email:
        text = text.replace(to_email, "[email]")
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())[:500]


def _recover_stale(db: Session, now: datetime) -> int:
    """将长时间处于 SENDING 状态的邮件恢复为 PENDING，返回恢复的数量"""
    cutoff = now - timedelta(seconds=settings.email_sending_timeout_seconds)
    result = db.execute(
        update(EmailOutbox)
        .where(
            EmailOutbox.status == EmailStatus.SENDING,
            EmailOutbox.update_time < cutoff,
        )
        .values(status=EmailStatus.PENDING, next_retry_at=now)
    )
    db.commit()
    recovered = result.rowcount or 0
    if recovered:
        logger.info(
            "email_outbox_recovered",
            extra={
                "request_id": "system:email",
                "changed_count": recovered,
            },
        )
    return recovered


def process_email_outbox(
    db: Session | None = None,
    *,
    now: datetime | None = None,
    sender=None,
    batch_size: int | None = None,
) -> int:
    """发送一批 outbox；返回本次实际处理的邮件数。"""
    owns_session = db is None
    if db is None:
        db = SessionLocal()

    now = now or datetime.now()
    batch_size = max(1, int(batch_size or settings.email_batch_size))
    delays = _retry_delays(settings.email_retry_delays)
    processed = 0

    try:
        sender = sender or build_email_sender(settings)
        _recover_stale(db, now)
        while True:
            started_at = time.perf_counter()
            candidate_ids = db.scalars(
                select(EmailOutbox.id)
                .where(
                    EmailOutbox.status == EmailStatus.PENDING,
                    or_(
                        EmailOutbox.next_retry_at.is_(None),
                        EmailOutbox.next_retry_at <= now,
                    ),
                )
                .order_by(EmailOutbox.id)
                .limit(batch_size)
            ).all()
            if not candidate_ids:
                break

            sent_count = 0
            failed_count = 0
            claimed_count = 0
            for outbox_id in candidate_ids:
                claim = db.execute(
                    update(EmailOutbox)
                    .where(
                        EmailOutbox.id == outbox_id,
                        EmailOutbox.status == EmailStatus.PENDING,
                    )
                    .values(
                        status=EmailStatus.SENDING,
                        attempts=EmailOutbox.attempts + 1,
                    )
                )
                db.commit()
                if claim.rowcount != 1:
                    continue
                claimed_count += 1

                outbox = db.get(EmailOutbox, outbox_id)
                if outbox is None:
                    continue

                try:
                    provider_message_id = sender.send(
                        outbox.to_email,
                        outbox.subject,
                        outbox.body,
                    )
                except Exception as exc:
                    outbox.last_error = _sanitize_error(exc, to_email=outbox.to_email)
                    if outbox.attempts >= outbox.max_attempts:
                        outbox.status = EmailStatus.FAILED
                        outbox.next_retry_at = None
                        failed_count += 1
                        logger.warning(
                            "email_outbox_failed",
                            extra={
                                "request_id": f"system:email:{outbox.id}",
                                "outbox_id": outbox.id,
                                "attempts": outbox.attempts,
                                "error_type": type(exc).__name__,
                            },
                        )
                    else:
                        delay = _retry_delay(outbox.attempts, delays)
                        outbox.status = EmailStatus.PENDING
                        outbox.next_retry_at = now + timedelta(seconds=delay)
                        failed_count += 1
                        logger.warning(
                            "email_outbox_retry_scheduled",
                            extra={
                                "request_id": f"system:email:{outbox.id}",
                                "outbox_id": outbox.id,
                                "attempts": outbox.attempts,
                                "error_type": type(exc).__name__,
                            },
                        )
                    db.commit()
                else:
                    outbox.status = EmailStatus.SENT
                    outbox.sent_at = now
                    outbox.provider_message_id = provider_message_id
                    outbox.last_error = None
                    db.commit()
                    sent_count += 1
                    logger.info(
                        "email_outbox_sent",
                        extra={
                            "request_id": f"system:email:{outbox.id}",
                            "outbox_id": outbox.id,
                            "attempts": outbox.attempts,
                        },
                    )
                processed += 1

            logger.info(
                "email_outbox_batch",
                extra={
                    "request_id": "system:email",
                    "candidate_count": len(candidate_ids),
                    "changed_count": sent_count,
                    "failed_count": failed_count,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
            if len(candidate_ids) < batch_size or claimed_count == 0:
                break

        return processed
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


async def run_email_outbox_scan(sender=None):
    """异步循环扫描 outbox 并发送邮件"""
    sender = sender or build_email_sender(settings)
    while True:
        try:
            process_email_outbox(sender=sender)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "email_outbox_scan_failed",
                extra={"request_id": "system:email"},
            )
        await asyncio.sleep(settings.email_worker_interval_seconds)
