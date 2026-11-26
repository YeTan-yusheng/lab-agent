from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import app as api_router
from app.core.database import get_db
from app.core.exceptions import BusinessException, register_exception_handlers
from app.core.middleware import RequestContextMiddleware
from app.core.password import hash_password
from app.core.reservation_lifecycle import (
    ReservationAction,
    ReservationErrorCode,
    ReservationStatus,
)
from app.models.base import Base
from app.models.reservation import Reservation
from app.models.reservation_status_history import ReservationStatusHistory
from app.models.user import User, UserRoles
from app.services import reservation_service

PASSWORD_HASH = hash_password("123456")


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


def _create_user(db, username, roles):
    user = User(
        username=username,
        password=PASSWORD_HASH,
        name=username,
        role=(
            "admin"
            if "admin" in roles
            else ("teacher" if "teacher" in roles else "student")
        ),
        status=1,
    )
    db.add(user)
    db.flush()
    for role_code in roles:
        db.add(UserRoles(user_id=user.id, role_code=role_code))
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def users(db):
    return {
        "student": _create_user(db, "cancel_student", ["student"]),
        "teacher": _create_user(db, "cancel_teacher", ["teacher"]),
        "admin": _create_user(db, "cancel_admin", ["admin"]),
        "teacher_admin": _create_user(
            db, "cancel_teacher_admin", ["teacher", "admin"]
        ),
    }


def _create_reservation(db, user_id, start_at, status=ReservationStatus.PENDING):
    end_at = start_at + timedelta(hours=1)
    item = Reservation(
        user_id=user_id,
        lab_id=1,
        date=start_at.date().isoformat(),
        start_time=start_at.strftime("%H:%M"),
        end_time=end_at.strftime("%H:%M"),
        status=status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _history(db, reservation_id):
    db.expire_all()
    return db.scalars(
        select(ReservationStatusHistory)
        .where(ReservationStatusHistory.reservation_id == reservation_id)
        .order_by(ReservationStatusHistory.id)
    ).all()


def _create_app(db):
    app = FastAPI()
    app.include_router(api_router)
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture()
def client(db):
    with TestClient(_create_app(db)) as test_client:
        yield test_client


def _login(client, username):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "123456"},
    )
    assert response.json()["code"] == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def test_owner_cancels_pending(db, users):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(db, users["student"].id, datetime(2026, 11, 25, 18, 0))

    reservation_service.cancel_reservation(
        db,
        reservation.id,
        users["student"],
        reason="临时有事",
        request_id="req-cancel-pending",
        now=now,
    )
    db.refresh(reservation)

    assert reservation.status == ReservationStatus.CANCELLED
    assert reservation.cancel_reason == "临时有事"
    assert reservation.cancelled_by == users["student"].id
    history = _history(db, reservation.id)
    assert len(history) == 1
    assert history[0].from_status == ReservationStatus.PENDING
    assert history[0].to_status == ReservationStatus.CANCELLED
    assert history[0].action == ReservationAction.CANCEL
    assert history[0].actor_id == users["student"].id
    assert history[0].request_id == "req-cancel-pending"


def test_owner_cancels_approved_with_more_than_12_hours(db, users):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db,
        users["student"].id,
        now + timedelta(hours=12, minutes=1),
        status=ReservationStatus.APPROVED,
    )

    reservation_service.cancel_reservation(
        db, reservation.id, users["student"], now=now
    )
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.CANCELLED


def test_owner_cancels_approved_exactly_12_hours(db, users):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db,
        users["student"].id,
        now + timedelta(hours=12),
        status=ReservationStatus.APPROVED,
    )

    reservation_service.cancel_reservation(
        db, reservation.id, users["student"], now=now
    )
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.CANCELLED


def test_owner_cannot_cancel_approved_with_less_than_12_hours(db, users):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db,
        users["student"].id,
        now + timedelta(hours=11, minutes=59),
        status=ReservationStatus.APPROVED,
    )

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.cancel_reservation(
            db, reservation.id, users["student"], now=now
        )

    assert exc_info.value.code == 409
    assert exc_info.value.error_code == ReservationErrorCode.CANCEL_TOO_LATE
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.APPROVED
    assert _history(db, reservation.id) == []


def test_owner_cannot_cancel_started_approved(db, users):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db,
        users["student"].id,
        now - timedelta(minutes=1),
        status=ReservationStatus.APPROVED,
    )

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.cancel_reservation(
            db, reservation.id, users["student"], now=now
        )

    assert exc_info.value.code == 409
    assert exc_info.value.error_code == ReservationErrorCode.CANCEL_TOO_LATE


@pytest.mark.parametrize("status", [2, 3, 4])
def test_terminal_reservation_cannot_be_cancelled(db, users, status):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db,
        users["student"].id,
        now + timedelta(days=1),
        status=status,
    )

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.cancel_reservation(
            db, reservation.id, users["student"], now=now
        )

    assert exc_info.value.code == 409
    assert exc_info.value.error_code == ReservationErrorCode.INVALID_STATUS_TRANSITION


def test_pending_reservation_can_be_cancelled_after_start(db, users):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db, users["student"].id, now - timedelta(minutes=30)
    )

    reservation_service.cancel_reservation(
        db, reservation.id, users["student"], now=now
    )
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.CANCELLED


def test_non_owner_cannot_cancel_normally(db, users):
    reservation = _create_reservation(
        db, users["student"].id, datetime(2026, 11, 25, 10, 0)
    )

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.cancel_reservation(
            db, reservation.id, users["teacher"]
        )

    assert exc_info.value.code == 403
    assert exc_info.value.error_code == ReservationErrorCode.FORBIDDEN


def test_admin_cannot_cancel_others_without_force(db, users):
    reservation = _create_reservation(
        db, users["student"].id, datetime(2026, 11, 25, 10, 0)
    )

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.cancel_reservation(
            db, reservation.id, users["admin"]
        )

    assert exc_info.value.code == 403
    assert exc_info.value.error_code == ReservationErrorCode.FORBIDDEN


def test_admin_force_cancels_other_reservation(db, users):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db, users["student"].id, datetime(2026, 11, 25, 10, 0)
    )

    reservation_service.cancel_reservation(
        db,
        reservation.id,
        users["admin"],
        reason="实验室临时关闭",
        force=True,
        request_id="req-force",
        now=now,
    )
    db.refresh(reservation)

    assert reservation.status == ReservationStatus.CANCELLED
    assert reservation.cancel_reason == "实验室临时关闭"
    assert reservation.cancelled_by == users["admin"].id
    history = _history(db, reservation.id)
    assert history[0].action == ReservationAction.FORCE_CANCEL
    assert history[0].reason == "实验室临时关闭"
    assert history[0].request_id == "req-force"


def test_force_cancel_requires_reason(db, users):
    reservation = _create_reservation(
        db, users["student"].id, datetime(2026, 11, 25, 10, 0)
    )

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.cancel_reservation(
            db, reservation.id, users["admin"], force=True
        )

    assert exc_info.value.code == 422
    assert exc_info.value.error_code == ReservationErrorCode.CANCEL_REASON_REQUIRED


def test_force_cancel_requires_audit_capability(db, users):
    reservation = _create_reservation(
        db, users["student"].id, datetime(2026, 11, 25, 10, 0)
    )

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.cancel_reservation(
            db,
            reservation.id,
            users["teacher"],
            reason="越权",
            force=True,
        )

    assert exc_info.value.code == 403
    assert exc_info.value.error_code == ReservationErrorCode.FORBIDDEN


def test_teacher_admin_can_force_cancel_own_inside_12_hours(db, users):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db,
        users["teacher_admin"].id,
        now + timedelta(hours=1),
        status=ReservationStatus.APPROVED,
    )

    reservation_service.cancel_reservation(
        db,
        reservation.id,
        users["teacher_admin"],
        reason="管理员本人调整",
        force=True,
        now=now,
    )
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.CANCELLED
    assert reservation.cancelled_by == users["teacher_admin"].id
    assert _history(db, reservation.id)[0].action == ReservationAction.FORCE_CANCEL


def test_cancel_missing_reservation_returns_404(db, users):
    with pytest.raises(BusinessException) as exc_info:
        reservation_service.cancel_reservation(db, 999999, users["student"])

    assert exc_info.value.code == 404
    assert exc_info.value.error_code == ReservationErrorCode.NOT_FOUND


def test_cancel_preserves_review_fields(db, users):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db,
        users["student"].id,
        now + timedelta(hours=20),
        status=ReservationStatus.APPROVED,
    )
    reservation.reviewer_id = users["admin"].id
    reservation.reviewed_at = now - timedelta(hours=1)
    db.commit()

    reservation_service.cancel_reservation(
        db, reservation.id, users["student"], now=now
    )
    db.refresh(reservation)
    assert reservation.reviewer_id == users["admin"].id
    assert reservation.reviewed_at == now - timedelta(hours=1)


def test_cancel_api_without_body(db, users, client):
    reservation = _create_reservation(
        db, users["student"].id, datetime(2026, 11, 25, 10, 0)
    )
    headers = _login(client, "cancel_student")
    headers["X-Request-ID"] = "req-api-cancel"

    response = client.put(
        f"/api/reservation/{reservation.id}/cancel",
        headers=headers,
    )

    assert response.status_code == 200
    db.expire_all()
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.CANCELLED
    history = _history(db, reservation.id)
    assert history[0].action == ReservationAction.CANCEL
    assert history[0].request_id == "req-api-cancel"


def test_admin_force_cancel_api(db, users, client):
    reservation = _create_reservation(
        db,
        users["student"].id,
        datetime(2099, 1, 1, 10, 0),
        status=ReservationStatus.APPROVED,
    )
    headers = _login(client, "cancel_admin")
    headers["X-Request-ID"] = "req-api-force"

    response = client.put(
        f"/api/reservation/{reservation.id}/cancel",
        json={"force": True, "reason": "设备故障"},
        headers=headers,
    )

    assert response.status_code == 200
    db.expire_all()
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.CANCELLED
    assert reservation.cancel_reason == "设备故障"
    assert reservation.cancelled_by == users["admin"].id
    assert _history(db, reservation.id)[0].request_id == "req-api-force"


def test_force_cancel_started_reservation_is_rejected(db, users):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db,
        users["student"].id,
        now - timedelta(minutes=1),
        status=ReservationStatus.APPROVED,
    )

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.cancel_reservation(
            db,
            reservation.id,
            users["admin"],
            reason="设备故障",
            force=True,
            now=now,
        )

    assert exc_info.value.code == 409
    assert exc_info.value.error_code == ReservationErrorCode.CANCEL_TOO_LATE
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.APPROVED
    assert _history(db, reservation.id) == []


def test_force_cancel_started_pending_is_rejected(db, users):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db,
        users["student"].id,
        now - timedelta(minutes=1),
        status=ReservationStatus.PENDING,
    )

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.cancel_reservation(
            db,
            reservation.id,
            users["admin"],
            reason="设备故障",
            force=True,
            now=now,
        )

    assert exc_info.value.code == 409
    assert exc_info.value.error_code == ReservationErrorCode.CANCEL_TOO_LATE
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.PENDING


def test_cancel_api_too_late(db, users, client):
    reservation = _create_reservation(
        db,
        users["student"].id,
        datetime.now() + timedelta(hours=1),
        status=ReservationStatus.APPROVED,
    )
    headers = _login(client, "cancel_student")

    response = client.put(
        f"/api/reservation/{reservation.id}/cancel",
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == ReservationErrorCode.CANCEL_TOO_LATE