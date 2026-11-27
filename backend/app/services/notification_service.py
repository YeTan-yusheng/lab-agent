import logging
from datetime import datetime
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessException
from app.core.notification_lifecycle import NotificationErrorCode, NotificationType
from app.core.reservation_lifecycle import ReservationAction
from app.core.response import PageResponse
from app.models.email_outbox import EmailOutbox
from app.models.lab import Lab
from app.models.notification import Notification
from app.models.user import User, UserRoles
from app.schemas.notification import NotificationItem

logger = logging.getLogger(__name__)

# 通知类型映射，用于站内信和邮件通知
ACTION_NOTIFICATION_TYPES = {
    ReservationAction.SUBMIT: NotificationType.RESERVATION_SUBMITTED,
    ReservationAction.APPROVE: NotificationType.RESERVATION_APPROVED,
    ReservationAction.REJECT: NotificationType.RESERVATION_REJECTED,
    ReservationAction.CANCEL: NotificationType.RESERVATION_CANCELLED,
    ReservationAction.FORCE_CANCEL: NotificationType.RESERVATION_FORCE_CANCELLED,
    ReservationAction.EXPIRE: NotificationType.RESERVATION_EXPIRED,
}

# 邮件通知操作
EMAIL_ACTIONS = {
    ReservationAction.APPROVE,
    ReservationAction.REJECT,
    ReservationAction.FORCE_CANCEL,
    ReservationAction.EXPIRE,
}


def notify_reservation_event(
    db: Session,
    *,
    reservation,
    action: ReservationAction,
    actor_id: int | None,
    reason: str | None,
    request_id: str | None,
) -> list[Notification]:
    """在业务事务内写站内信和邮件 outbox，不提交事务"""
    action = ReservationAction(action)
    notification_type = ACTION_NOTIFICATION_TYPES.get(action)
    if notification_type is None:
        return []

    recipients = _resolve_recipients(db, reservation, action, actor_id)
    if not recipients:
        return []

    lab = db.get(Lab, reservation.lab_id)
    lab_name = lab.name if lab else "实验室"
    actor = db.get(User, actor_id) if actor_id is not None else None
    actor_name = actor.name if actor else "用户"
    title, content = _build_message(
        reservation, action, reason, lab_name=lab_name, actor_name=actor_name
    )

    created = []
    for recipient in recipients:
        inapp_key, email_key = _dedupe_keys(reservation.id, action, recipient.id)
        if _exists(db, Notification, inapp_key):
            continue

        notification = Notification(
            user_id=recipient.id,
            type=notification_type.value,
            title=title,
            content=content,
            reservation_id=reservation.id,
            dedupe_key=inapp_key,
        )
        if not _insert_with_savepoint(db, notification, inapp_key):
            continue
        created.append(notification)
        logger.info(
            "notification_created",
            extra={
                "request_id": request_id,
                "notification_id": notification.id,
                "reservation_id": reservation.id,
                "action": action.value,
                "user_id": recipient.id,
            },
        )

        if (
            action in EMAIL_ACTIONS
            and recipient.email
            and not _exists(db, EmailOutbox, email_key)
        ):
            outbox = EmailOutbox(
                notification_id=notification.id,
                to_email=recipient.email,
                subject=title,
                body=content,
                dedupe_key=email_key,
            )
            if _insert_with_savepoint(db, outbox, email_key):
                logger.info(
                    "email_outbox_enqueued",
                    extra={
                        "request_id": request_id,
                        "outbox_id": outbox.id,
                        "notification_id": notification.id,
                    },
                )
    return created


def _resolve_recipients(db, reservation, action, actor_id):
    """根据预约操作和用户角色，确定通知接收人"""
    if action == ReservationAction.CANCEL:
        return []

    if action == ReservationAction.SUBMIT:
        stmt = (
            select(User)
            .join(UserRoles, UserRoles.user_id == User.id)
            .where(
                UserRoles.role_code == "admin",
                User.status == 1,
            )
        )
        if actor_id is not None:
            stmt = stmt.where(User.id != actor_id)
        return list(db.scalars(stmt).unique().all())

    owner = db.get(User, reservation.user_id)
    if owner is None or owner.status != 1:
        logger.warning(
            "notification_recipient_missing",
            extra={"reservation_id": reservation.id, "user_id": reservation.user_id},
        )
        return []
    if actor_id is not None and owner.id == actor_id:
        return []
    return [owner]


def _build_message(reservation, action, reason, *, lab_name, actor_name):
    """根据预约操作，构建通知标题和内容"""
    when = f"{reservation.date} {reservation.start_time}-{reservation.end_time}"
    reason_text = reason or "未填写"
    if action == ReservationAction.SUBMIT:
        return (
            "新的待审核预约",
            f"{actor_name} 提交了 {lab_name} {when} 的预约，请及时审核。",
        )
    if action == ReservationAction.APPROVE:
        return (
            "预约已通过",
            f"你预约的 {lab_name} {when} 已通过审核。",
        )
    if action == ReservationAction.REJECT:
        return (
            "预约已拒绝",
            f"你预约的 {lab_name} {when} 已被拒绝，原因：{reason_text}。",
        )
    if action == ReservationAction.FORCE_CANCEL:
        return (
            "预约已被取消",
            f"你预约的 {lab_name} {when} 已被管理员取消，原因：{reason_text}。",
        )
    if action == ReservationAction.EXPIRE:
        return (
            "预约已过期",
            f"你预约的 {lab_name} {when} 因待审核超时已过期。",
        )
    return "预约状态更新", f"你预约的 {lab_name} {when} 状态已更新。"


def _dedupe_keys(reservation_id: int, action: ReservationAction, user_id: int):
    """生成站内信和邮件的幂等键"""
    prefix = f"resv:{reservation_id}:{action.value}:user:{user_id}"
    return f"{prefix}:inapp", f"{prefix}:email"


def _exists(db: Session, model: Notification | EmailOutbox, dedupe_key: str) -> bool:
    """检查指定的幂等键是否已存在于数据库中"""
    return db.scalar(select(model.id).where(model.dedupe_key == dedupe_key)) is not None


def get_notification_page_list(
    db: Session,
    current_user: User,
    *,
    page: int,
    page_size: int,
    is_read: bool | None = None,
):
    """查询当前用户的站内信分页列表"""
    stmt = select(Notification).where(Notification.user_id == current_user.id)
    if is_read is not None:
        stmt = stmt.where(Notification.is_read == is_read)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(
        stmt.order_by(Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PageResponse(
        list=[NotificationItem.model_validate(item) for item in items],
        total=total or 0,
    )


def get_unread_count(db: Session, current_user: User) -> int:
    """统计当前用户的未读站内信数量"""
    return (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == current_user.id,
                Notification.is_read.is_(False),
            )
        )
        or 0
    )


def mark_notification_read(
    db: Session,
    current_user: User,
    notification_id: int,
) -> None:
    """将当前用户的一条站内信标记为已读"""
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != current_user.id:
        raise BusinessException(
            code=404,
            message="通知不存在",
            error_code=NotificationErrorCode.NOT_FOUND.value,
        )
    if notification.is_read:
        return
    notification.is_read = True
    notification.read_at = datetime.now()
    db.commit()


def mark_all_notifications_read(db: Session, current_user: User) -> int:
    """将当前用户的全部未读站内信标记为已读"""
    result = db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=datetime.now())
    )
    db.commit()
    return result.rowcount or 0


def _insert_with_savepoint(db: Session, obj, dedupe_key: str) -> bool:
    """尝试在事务中插入对象，如果违反唯一约束则回滚到保存点"""
    try:
        with db.begin_nested():
            db.add(obj)
            db.flush()
        return True
    except IntegrityError:
        if obj in db:
            db.expunge(obj)
        logger.info(
            "notification_insert_skipped",
            extra={"dedupe_key": dedupe_key},
        )
        return False
