import logging
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.notification_lifecycle import EmailStatus
from app.models.base import Base
from app.models.email_outbox import EmailOutbox
from app.services.email_outbox_service import process_email_outbox
from app.services.email_sender import (
    ConsoleEmailSender,
    EmailSendError,
    build_email_sender,
)

NOW = datetime(2026, 11, 26, 12, 0)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class FakeSender:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls = []

    def send(self, to_email, subject, body):
        self.calls.append((to_email, subject, body))
        if self.results:
            result = self.results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
        return f"fake:{len(self.calls)}"


def _outbox(**overrides):
    values = {
        "to_email": "user@example.com",
        "subject": "预约已通过",
        "body": "你预约的实验室已通过。",
        "status": EmailStatus.PENDING,
        "attempts": 0,
        "max_attempts": 3,
        "dedupe_key": f"test:{uuid.uuid4().hex}",
    }
    values.update(overrides)
    return EmailOutbox(**values)


def test_sends_pending_email(db):
    item = _outbox()
    db.add(item)
    db.commit()
    sender = FakeSender(["message-1"])

    processed = process_email_outbox(
        db,
        now=NOW,
        sender=sender,
        batch_size=10,
    )

    assert processed == 1
    db.expire_all()
    loaded = db.get(EmailOutbox, item.id)
    assert loaded.status == EmailStatus.SENT
    assert loaded.attempts == 1
    assert loaded.sent_at == NOW
    assert loaded.provider_message_id == "message-1"
    assert loaded.last_error is None
    assert sender.calls[0][0] == "user@example.com"


def test_failure_schedules_retry_then_succeeds(db):
    item = _outbox()
    db.add(item)
    db.commit()
    sender = FakeSender([EmailSendError("smtp down"), "message-2"])

    assert process_email_outbox(db, now=NOW, sender=sender) == 1
    db.expire_all()
    loaded = db.get(EmailOutbox, item.id)
    assert loaded.status == EmailStatus.PENDING
    assert loaded.attempts == 1
    assert loaded.next_retry_at == NOW + timedelta(seconds=60)
    assert "smtp down" in loaded.last_error

    assert (
        process_email_outbox(
            db,
            now=NOW + timedelta(seconds=59),
            sender=sender,
        )
        == 0
    )
    assert (
        process_email_outbox(
            db,
            now=NOW + timedelta(seconds=60),
            sender=sender,
        )
        == 1
    )
    db.expire_all()
    loaded = db.get(EmailOutbox, item.id)
    assert loaded.status == EmailStatus.SENT
    assert loaded.attempts == 2


def test_failure_reaches_max_attempts(db):
    item = _outbox(max_attempts=1)
    db.add(item)
    db.commit()
    sender = FakeSender([EmailSendError("permanent failure")])

    assert process_email_outbox(db, now=NOW, sender=sender) == 1

    db.expire_all()
    loaded = db.get(EmailOutbox, item.id)
    assert loaded.status == EmailStatus.FAILED
    assert loaded.attempts == 1
    assert loaded.next_retry_at is None
    assert "permanent failure" in loaded.last_error


def test_failure_error_is_sanitized(db):
    item = _outbox(max_attempts=2)
    db.add(item)
    db.commit()
    sender = FakeSender([EmailSendError("failed for user@example.com\nstack line")])

    process_email_outbox(db, now=NOW, sender=sender)

    db.expire_all()
    loaded = db.get(EmailOutbox, item.id)
    assert "user@example.com" not in loaded.last_error
    assert "[email]" in loaded.last_error
    assert "\n" not in loaded.last_error


def test_stale_sending_is_recovered_and_sent(db):
    item = _outbox(
        status=EmailStatus.SENDING,
        attempts=1,
        update_time=NOW - timedelta(minutes=20),
    )
    db.add(item)
    db.commit()
    sender = FakeSender(["recovered-message"])

    assert process_email_outbox(db, now=NOW, sender=sender) == 1

    db.expire_all()
    loaded = db.get(EmailOutbox, item.id)
    assert loaded.status == EmailStatus.SENT
    assert loaded.provider_message_id == "recovered-message"


def test_batch_continues_after_one_failure(db):
    first = _outbox(max_attempts=2)
    second = _outbox(max_attempts=2)
    third = _outbox(max_attempts=2)
    db.add_all([first, second, third])
    db.commit()
    sender = FakeSender(["ok-1", EmailSendError("bad"), "ok-3"])

    assert process_email_outbox(db, now=NOW, sender=sender, batch_size=10) == 3

    db.expire_all()
    assert db.get(EmailOutbox, first.id).status == EmailStatus.SENT
    assert db.get(EmailOutbox, second.id).status == EmailStatus.PENDING
    assert db.get(EmailOutbox, third.id).status == EmailStatus.SENT


def test_sending_rows_are_not_claimed(db):
    item = _outbox(status=EmailStatus.SENDING, update_time=NOW)
    db.add(item)
    db.commit()
    sender = FakeSender()

    assert process_email_outbox(db, now=NOW, sender=sender) == 0
    assert sender.calls == []
    db.expire_all()
    assert db.get(EmailOutbox, item.id).status == EmailStatus.SENDING


def test_console_sender_does_not_log_full_email(db, caplog):
    caplog.set_level(logging.INFO)
    sender = ConsoleEmailSender()

    message_id = sender.send("user@example.com", "预约已通过", "正文")

    assert message_id.startswith("console:")
    assert "user@example.com" not in caplog.text
    record = next(
        item for item in caplog.records if item.getMessage() == "email_console_sent"
    )
    assert record.to_domain == "example.com"
    assert record.subject_len == len("预约已通过")


def test_smtp_backend_requires_host():
    settings = SimpleNamespace(
        email_backend="smtp",
        smtp_host=None,
        smtp_port=587,
        email_from="noreply@lab.local",
        smtp_username=None,
        smtp_auth_code=None,
        smtp_use_tls=True,
        smtp_timeout_seconds=10,
    )

    with pytest.raises(ValueError, match="SMTP_HOST"):
        build_email_sender(settings)


def test_unknown_backend_is_rejected():
    settings = SimpleNamespace(
        email_backend="unknown",
        smtp_host=None,
        smtp_port=587,
        email_from="noreply@lab.local",
        smtp_username=None,
        smtp_auth_code=None,
        smtp_use_tls=True,
        smtp_timeout_seconds=10,
    )

    with pytest.raises(ValueError, match="未知 EMAIL_BACKEND"):
        build_email_sender(settings)
