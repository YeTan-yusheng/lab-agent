from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.notification_lifecycle import (
    EmailStatus,
    NotificationErrorCode,
    NotificationType,
)
from app.models import EmailOutbox, Lab, Notification, Reservation, User
from app.models.base import Base


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed(db):
    user = User(
        username="notification_user",
        password="hashed",
        name="通知用户",
        role="student",
        email="user@example.com",
    )
    lab = Lab(
        name="通知测试实验室",
        location="A101",
        capacity=10,
        open_time="08:00",
        close_time="18:00",
        status=1,
    )
    db.add_all([user, lab])
    db.flush()
    reservation = Reservation(
        user_id=user.id,
        lab_id=lab.id,
        date="2099-01-01",
        start_time="09:00",
        end_time="10:00",
        status=0,
    )
    db.add(reservation)
    db.flush()
    return user, lab, reservation


def _notification(user, reservation=None, **overrides):
    values = {
        "user_id": user.id,
        "type": NotificationType.RESERVATION_SUBMITTED,
        "title": "新的待审核预约",
        "content": "有一条新的预约待审核。",
        "reservation_id": reservation.id if reservation is not None else None,
        "dedupe_key": "resv:1:submit:user:1:inapp",
    }
    values.update(overrides)
    return Notification(**values)


def _outbox(notification=None, **overrides):
    values = {
        "notification_id": notification.id if notification is not None else None,
        "to_email": "user@example.com",
        "subject": "预约已通过",
        "body": "你的预约已通过。",
        "dedupe_key": "resv:1:approve:user:1:email",
    }
    values.update(overrides)
    return EmailOutbox(**values)


def test_notification_enums():
    assert NotificationType.RESERVATION_APPROVED == "reservation_approved"
    assert NotificationType.RESERVATION_FORCE_CANCELLED == "reservation_force_cancelled"
    assert EmailStatus.PENDING == 0
    assert EmailStatus.SENT == 2
    assert EmailStatus.FAILED == 3
    assert NotificationErrorCode.NOT_FOUND == "NOTIFICATION_NOT_FOUND"
    assert NotificationErrorCode.SEND_FAILED == "EMAIL_SEND_FAILED"


def test_notification_defaults(db):
    user, _, reservation = _seed(db)
    notification = _notification(user, reservation)
    db.add(notification)
    db.flush()

    assert notification.id is not None
    assert notification.is_read is False
    assert notification.read_at is None
    assert notification.reservation_id == reservation.id


def test_notification_can_be_marked_read(db):
    user, _, _ = _seed(db)
    read_at = datetime(2026, 11, 26, 18, 30)
    notification = _notification(user, is_read=True, read_at=read_at)
    db.add(notification)
    db.commit()
    db.refresh(notification)

    assert notification.is_read is True
    assert notification.read_at == read_at


def test_notification_dedupe_key_is_unique(db):
    user, _, _ = _seed(db)
    db.add_all(
        [
            _notification(user, dedupe_key="resv:1:approve:user:1:inapp"),
            _notification(user, dedupe_key="resv:1:approve:user:1:inapp"),
        ]
    )

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_notification_foreign_keys(db):
    user, _, reservation = _seed(db)

    db.add(_notification(user, reservation, user_id=9999))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add(_notification(user, reservation, reservation_id=9999))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_notification_relationships(db):
    user, _, reservation = _seed(db)
    notification = _notification(user, reservation)
    db.add(notification)
    db.flush()
    outbox = _outbox(notification)
    db.add(outbox)
    db.commit()
    db.expire_all()

    loaded = db.scalars(
        select(Notification).where(Notification.id == notification.id)
    ).one()
    assert loaded.user.name == "通知用户"
    assert loaded.reservation.id == reservation.id

    loaded_outbox = db.scalars(
        select(EmailOutbox).where(EmailOutbox.id == outbox.id)
    ).one()
    assert loaded_outbox.notification.id == notification.id


def test_notification_is_not_cascade_deleted_with_reservation(db):
    user, _, reservation = _seed(db)
    db.add(_notification(user, reservation))
    db.commit()

    db.delete(reservation)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_email_outbox_defaults(db):
    user, _, _ = _seed(db)
    notification = _notification(user)
    db.add(notification)
    db.flush()

    outbox = _outbox(notification)
    db.add(outbox)
    db.flush()

    assert outbox.status == EmailStatus.PENDING
    assert outbox.attempts == 0
    assert outbox.max_attempts == 5
    assert outbox.next_retry_at is None
    assert outbox.last_error is None
    assert outbox.sent_at is None
    assert outbox.provider_message_id is None


def test_email_outbox_dedupe_key_is_unique(db):
    user, _, _ = _seed(db)
    db.add_all(
        [
            _outbox(
                to_email="a@example.com",
                dedupe_key="resv:1:approve:user:1:email",
            ),
            _outbox(
                to_email="b@example.com",
                dedupe_key="resv:1:approve:user:1:email",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": 4},
        {"attempts": -1},
        {"max_attempts": 0},
    ],
)
def test_email_outbox_check_constraints(db, overrides):
    user, _, _ = _seed(db)
    db.add(_outbox(**overrides))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_email_outbox_foreign_key(db):
    db.add(_outbox(notification_id=9999))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_notification_tables_indexes(db):
    inspector = inspect(db.bind)

    notification_indexes = {
        index["name"] for index in inspector.get_indexes("notifications")
    }
    outbox_indexes = {
        index["name"] for index in inspector.get_indexes("email_outbox")
    }
    notification_uniques = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("notifications")
    }
    outbox_uniques = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints("email_outbox")
    }

    assert "ix_notifications_user_read_id" in notification_indexes
    assert "ix_notifications_user_id_id" in notification_indexes
    assert "ix_notifications_reservation_id" in notification_indexes
    assert ("dedupe_key",) in notification_uniques

    assert "ix_email_outbox_status_retry_id" in outbox_indexes
    assert "ix_email_outbox_to_email_id" in outbox_indexes
    assert "ix_email_outbox_notification_id" in outbox_indexes
    assert ("dedupe_key",) in outbox_uniques