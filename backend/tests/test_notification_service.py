from datetime import datetime

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.exceptions import BusinessException
from app.core.notification_lifecycle import EmailStatus, NotificationType
from app.core.password import hash_password
from app.core.reservation_lifecycle import ReservationAction, ReservationStatus
from app.models import (
    EmailOutbox,
    Lab,
    Notification,
    Reservation,
    ReservationStatusHistory,
    User,
    UserRoles,
)
from app.models.base import Base
from app.schemas.reservation import ReservationCreateRequest
from app.services import notification_service, reservation_service


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


def _user(db, username, roles, *, email=None, status=1):
    user = User(
        username=username,
        password=hash_password("123456"),
        name=username,
        role="admin" if "admin" in roles else ("teacher" if "teacher" in roles else "student"),
        email=email,
        status=status,
    )
    db.add(user)
    db.flush()
    for role_code in roles:
        db.add(UserRoles(user_id=user.id, role_code=role_code))
    db.flush()
    return user


def _lab(db, name="通知实验室"):
    lab = Lab(
        name=name,
        location="B201",
        capacity=10,
        open_time="08:00",
        close_time="18:00",
        status=1,
    )
    db.add(lab)
    db.flush()
    return lab


def _reservation(db, owner, lab, *, remark="内部备注", date="2099-01-01"):
    reservation = Reservation(
        user_id=owner.id,
        lab_id=lab.id,
        date=date,
        start_time="09:00",
        end_time="10:00",
        remark=remark,
        status=ReservationStatus.PENDING,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _notify(db, reservation, action, *, actor=None, reason=None, request_id="req-1"):
    return notification_service.notify_reservation_event(
        db,
        reservation=reservation,
        action=action,
        actor_id=actor.id if actor else None,
        reason=reason,
        request_id=request_id,
    )


def _notifications(db):
    return db.scalars(select(Notification).order_by(Notification.id)).all()


def test_submit_notifies_enabled_admins_only(db):
    owner = _user(db, "student_owner", ["student"])
    admin = _user(db, "admin_user", ["admin"], email="admin@example.com")
    _user(db, "teacher_user", ["teacher"], email="teacher@example.com")
    _user(db, "disabled_admin", ["admin"], email="disabled@example.com", status=0)
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    created = _notify(db, reservation, ReservationAction.SUBMIT, actor=owner)
    db.commit()

    assert [item.user_id for item in created] == [admin.id]
    items = _notifications(db)
    assert len(items) == 1
    assert items[0].type == NotificationType.RESERVATION_SUBMITTED
    assert items[0].is_read is False
    assert items[0].reservation_id == reservation.id
    assert "通知实验室" in items[0].content
    assert "内部备注" not in items[0].content
    assert db.scalar(select(func.count()).select_from(EmailOutbox)) == 0


def test_submit_excludes_actor_even_if_admin(db):
    owner_admin = _user(db, "owner_admin", ["teacher", "admin"])
    other_admin = _user(db, "other_admin", ["admin"])
    lab = _lab(db)
    reservation = _reservation(db, owner_admin, lab)

    _notify(db, reservation, ReservationAction.SUBMIT, actor=owner_admin)
    db.commit()

    items = _notifications(db)
    assert [item.user_id for item in items] == [other_admin.id]


def test_approve_creates_inapp_and_email_outbox(db):
    owner = _user(db, "approved_owner", ["student"], email="owner@example.com")
    admin = _user(db, "approve_admin", ["admin"])
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    _notify(db, reservation, ReservationAction.APPROVE, actor=admin)
    db.commit()

    items = _notifications(db)
    assert len(items) == 1
    assert items[0].user_id == owner.id
    assert items[0].type == NotificationType.RESERVATION_APPROVED

    outboxes = db.scalars(select(EmailOutbox)).all()
    assert len(outboxes) == 1
    assert outboxes[0].notification_id == items[0].id
    assert outboxes[0].to_email == "owner@example.com"
    assert outboxes[0].status == EmailStatus.PENDING
    assert outboxes[0].subject == "预约已通过"


def test_reject_includes_reason_and_email(db):
    owner = _user(db, "reject_owner", ["student"], email="reject@example.com")
    admin = _user(db, "reject_admin", ["admin"])
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    _notify(
        db,
        reservation,
        ReservationAction.REJECT,
        actor=admin,
        reason="设备维护",
    )
    db.commit()

    item = _notifications(db)[0]
    assert item.type == NotificationType.RESERVATION_REJECTED
    assert "设备维护" in item.content
    assert db.scalars(select(EmailOutbox)).one().status == EmailStatus.PENDING


def test_owner_cancel_does_not_notify_self(db):
    owner = _user(db, "cancel_owner", ["student"], email="cancel@example.com")
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    _notify(db, reservation, ReservationAction.CANCEL, actor=owner)
    db.commit()

    assert _notifications(db) == []
    assert db.scalar(select(func.count()).select_from(EmailOutbox)) == 0


def test_force_cancel_notifies_owner_once(db):
    owner = _user(db, "force_owner", ["student"], email="force@example.com")
    admin = _user(db, "force_admin", ["admin"])
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    _notify(
        db,
        reservation,
        ReservationAction.FORCE_CANCEL,
        actor=admin,
        reason="实验室临时关闭",
    )
    db.commit()

    item = _notifications(db)[0]
    assert item.type == NotificationType.RESERVATION_FORCE_CANCELLED
    assert "实验室临时关闭" in item.content
    assert db.scalars(select(EmailOutbox)).one().to_email == "force@example.com"


def test_force_cancel_by_owner_skips(db):
    owner = _user(db, "force_self", ["teacher", "admin"])
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    _notify(db, reservation, ReservationAction.FORCE_CANCEL, actor=owner, reason="自己取消")
    db.commit()

    assert _notifications(db) == []


def test_expire_notifies_owner(db):
    owner = _user(db, "expire_owner", ["student"], email="expire@example.com")
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    _notify(db, reservation, ReservationAction.EXPIRE)
    db.commit()

    item = _notifications(db)[0]
    assert item.type == NotificationType.RESERVATION_EXPIRED
    assert "待审核超时" in item.content
    assert db.scalars(select(EmailOutbox)).one().status == EmailStatus.PENDING


def test_duplicate_event_is_idempotent(db):
    owner = _user(db, "dup_owner", ["student"], email="dup@example.com")
    admin = _user(db, "dup_admin", ["admin"])
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    _notify(db, reservation, ReservationAction.APPROVE, actor=admin)
    _notify(db, reservation, ReservationAction.APPROVE, actor=admin)
    db.commit()

    assert len(_notifications(db)) == 1
    assert db.scalar(select(func.count()).select_from(EmailOutbox)) == 1


def test_no_email_still_creates_inapp(db):
    owner = _user(db, "no_email_owner", ["student"])
    admin = _user(db, "no_email_admin", ["admin"])
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    _notify(db, reservation, ReservationAction.APPROVE, actor=admin)
    db.commit()

    assert len(_notifications(db)) == 1
    assert db.scalar(select(func.count()).select_from(EmailOutbox)) == 0


def test_disabled_owner_does_not_receive_result(db):
    owner = _user(db, "disabled_owner", ["student"], status=0)
    admin = _user(db, "enabled_admin", ["admin"])
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    _notify(db, reservation, ReservationAction.APPROVE, actor=admin)
    db.commit()

    assert _notifications(db) == []


def test_status_change_hook_creates_notification(db):
    owner = _user(db, "hook_owner", ["student"])
    admin = _user(db, "hook_admin", ["admin"])
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    reservation_service._record_status_change(
        db,
        reservation,
        from_status=None,
        to_status=ReservationStatus.PENDING,
        action=ReservationAction.SUBMIT,
        actor_id=owner.id,
        request_id="req-hook",
    )
    db.commit()

    items = _notifications(db)
    assert [item.user_id for item in items] == [admin.id]
    assert db.scalars(select(ReservationStatusHistory)).one().request_id == "req-hook"


def test_audit_service_creates_owner_notification(db):
    owner = _user(db, "audit_owner", ["student"], email="audit@example.com")
    admin = _user(db, "audit_admin", ["admin"])
    lab = _lab(db)
    reservation = _reservation(db, owner, lab)

    reservation_service.audit_reservation(
        db,
        admin,
        reservation.id,
        status=ReservationStatus.APPROVED,
        request_id="req-audit",
    )

    item = _notifications(db)[0]
    assert item.user_id == owner.id
    assert item.type == NotificationType.RESERVATION_APPROVED
    assert db.scalars(select(EmailOutbox)).one().to_email == "audit@example.com"


def test_expire_service_notifies_owner_and_is_idempotent(db):
    owner = _user(db, "expire_service_owner", ["student"], email="expire-service@example.com")
    _user(db, "expire_service_admin", ["admin"])
    lab = _lab(db)
    _reservation(db, owner, lab, date="2020-01-01")
    db.commit()

    total = reservation_service.expire_pending_reservations(
        db,
        now=datetime(2026, 11, 26, 12, 0),
        batch_size=10,
    )
    assert total == 1
    item = _notifications(db)[0]
    assert item.type == NotificationType.RESERVATION_EXPIRED
    assert db.scalars(select(EmailOutbox)).one().to_email == "expire-service@example.com"

    total = reservation_service.expire_pending_reservations(
        db,
        now=datetime(2026, 11, 26, 12, 1),
        batch_size=10,
    )
    assert total == 0
    assert len(_notifications(db)) == 1
    assert db.scalar(select(func.count()).select_from(EmailOutbox)) == 1


def test_notification_failure_rolls_back_business(db, monkeypatch):
    owner = _user(db, "rollback_owner", ["teacher"])
    _user(db, "rollback_admin", ["admin"])
    lab = _lab(db)

    def boom(*args, **kwargs):
        raise RuntimeError("notification failed")

    monkeypatch.setattr(reservation_service, "notify_reservation_event", boom)

    with pytest.raises(BusinessException) as exc:
        reservation_service.create_reservation(
            db,
            owner,
            ReservationCreateRequest(
                lab_id=lab.id,
                date="2099-01-01",
                start_time="09:00",
                end_time="10:00",
            ),
            request_id="req-rollback",
        )

    assert exc.value.code == 500
    assert db.scalar(select(func.count()).select_from(Reservation)) == 0
    assert db.scalar(select(func.count()).select_from(ReservationStatusHistory)) == 0
    assert db.scalar(select(func.count()).select_from(Notification)) == 0