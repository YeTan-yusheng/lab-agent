from datetime import datetime

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
from app.models.equipment import Equipment
from app.models.lab import Lab
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
        "student": _create_user(db, "audit_student", ["student"]),
        "teacher": _create_user(db, "audit_teacher", ["teacher"]),
        "admin": _create_user(db, "audit_admin", ["admin"]),
        "teacher_admin": _create_user(
            db, "audit_teacher_admin", ["teacher", "admin"]
        ),
    }


@pytest.fixture()
def reservation(db, users):
    item = Reservation(
        user_id=users["student"].id,
        lab_id=1,
        date="2099-01-01",
        start_time="10:00",
        end_time="11:00",
        status=ReservationStatus.PENDING,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture()
def lab_equipment(db):
    lab = Lab(
        name="审核测试实验室",
        location="C301",
        capacity=20,
        open_time="08:00",
        close_time="18:00",
        status=1,
    )
    db.add(lab)
    db.flush()
    equipment = Equipment(
        lab_id=lab.id,
        name="审核测试设备",
        spec="A-1",
        quantity=1,
        status=1,
    )
    db.add(equipment)
    db.commit()
    db.refresh(lab)
    db.refresh(equipment)
    return lab, equipment


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


def _booking_payload(lab, equipment=None, **overrides):
    payload = {
        "lab_id": lab.id,
        "date": "2099-01-01",
        "start_time": "10:00",
        "end_time": "11:00",
    }
    if equipment is not None:
        payload["equipment_id"] = equipment.id
    payload.update(overrides)
    return payload


def test_admin_approves_other_reservation(db, users, reservation):
    now = datetime(2026, 11, 24, 12, 0)

    reservation_service.audit_reservation(
        db,
        users["admin"],
        reservation.id,
        1,
        request_id="req-approve",
        now=now,
    )
    db.refresh(reservation)

    assert reservation.status == ReservationStatus.APPROVED
    assert reservation.reviewer_id == users["admin"].id
    assert reservation.reviewed_at == now
    assert reservation.reject_reason is None
    assert reservation.self_audit is False

    history = _history(db, reservation.id)
    assert len(history) == 1
    assert history[0].from_status == ReservationStatus.PENDING
    assert history[0].to_status == ReservationStatus.APPROVED
    assert history[0].action == ReservationAction.APPROVE
    assert history[0].actor_id == users["admin"].id
    assert history[0].request_id == "req-approve"


def test_admin_rejects_with_reason(db, users, reservation):
    reservation_service.audit_reservation(
        db,
        users["admin"],
        reservation.id,
        2,
        reject_reason="  不符合开放要求  ",
        request_id="req-reject",
    )
    db.refresh(reservation)

    assert reservation.status == ReservationStatus.REJECTED
    assert reservation.reject_reason == "不符合开放要求"
    assert reservation.self_audit is False
    history = _history(db, reservation.id)
    assert history[0].to_status == ReservationStatus.REJECTED
    assert history[0].action == ReservationAction.REJECT
    assert history[0].reason == "不符合开放要求"


def test_reject_requires_reason(db, users, reservation):
    with pytest.raises(BusinessException) as exc_info:
        reservation_service.audit_reservation(
            db, users["admin"], reservation.id, 2, reject_reason="   "
        )

    assert exc_info.value.code == 422
    assert exc_info.value.error_code == ReservationErrorCode.REJECT_REASON_REQUIRED
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.PENDING
    assert _history(db, reservation.id) == []


def test_approve_cannot_carry_reject_reason(db, users, reservation):
    with pytest.raises(BusinessException) as exc_info:
        reservation_service.audit_reservation(
            db, users["admin"], reservation.id, 1, reject_reason="原因"
        )

    assert exc_info.value.code == 422
    assert exc_info.value.error_code == ReservationErrorCode.REJECT_REASON_NOT_ALLOWED


def test_invalid_audit_status(db, users, reservation):
    with pytest.raises(BusinessException) as exc_info:
        reservation_service.audit_reservation(db, users["admin"], reservation.id, 3)

    assert exc_info.value.code == 422
    assert exc_info.value.error_code == ReservationErrorCode.INVALID_AUDIT_STATUS


def test_audit_missing_reservation_returns_404(db, users):
    with pytest.raises(BusinessException) as exc_info:
        reservation_service.audit_reservation(db, users["admin"], 999999, 1)

    assert exc_info.value.code == 404
    assert exc_info.value.error_code == ReservationErrorCode.NOT_FOUND


def test_repeated_audit_returns_409(db, users, reservation):
    reservation_service.audit_reservation(
        db, users["admin"], reservation.id, 1, request_id="req-first"
    )

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.audit_reservation(
            db, users["admin"], reservation.id, 2, reject_reason="重复审核"
        )

    assert exc_info.value.code == 409
    assert exc_info.value.error_code == ReservationErrorCode.INVALID_STATUS_TRANSITION
    assert len(_history(db, reservation.id)) == 1


def test_teacher_without_audit_capability_is_forbidden(db, users, reservation):
    with pytest.raises(BusinessException) as exc_info:
        reservation_service.audit_reservation(
            db, users["teacher"], reservation.id, 1
        )

    assert exc_info.value.code == 403
    assert exc_info.value.error_code == ReservationErrorCode.FORBIDDEN


def test_teacher_admin_self_audit_requires_flag(db, users):
    own = Reservation(
        user_id=users["teacher_admin"].id,
        lab_id=1,
        date="2099-01-02",
        start_time="09:00",
        end_time="10:00",
        status=ReservationStatus.PENDING,
    )
    db.add(own)
    db.commit()

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.audit_reservation(
            db, users["teacher_admin"], own.id, 1
        )
    assert exc_info.value.code == 403
    assert exc_info.value.error_code == ReservationErrorCode.SELF_AUDIT_REQUIRED

    reservation_service.audit_reservation(
        db,
        users["teacher_admin"],
        own.id,
        1,
        self_audit=True,
        request_id="req-self",
    )
    db.refresh(own)
    assert own.status == ReservationStatus.APPROVED
    assert own.self_audit is True
    assert own.reviewer_id == users["teacher_admin"].id

    history = _history(db, own.id)
    assert history[0].actor_id == users["teacher_admin"].id
    assert history[0].request_id == "req-self"


def test_teacher_admin_self_reject_keeps_self_audit_false(db, users):
    own = Reservation(
        user_id=users["teacher_admin"].id,
        lab_id=1,
        date="2099-01-03",
        start_time="09:00",
        end_time="10:00",
        status=ReservationStatus.PENDING,
    )
    db.add(own)
    db.commit()

    reservation_service.audit_reservation(
        db,
        users["teacher_admin"],
        own.id,
        2,
        reject_reason="本人取消安排",
        self_audit=True,
    )
    db.refresh(own)
    assert own.status == ReservationStatus.REJECTED
    assert own.self_audit is False


def test_self_audit_flag_on_other_reservation_is_invalid(db, users, reservation):
    with pytest.raises(BusinessException) as exc_info:
        reservation_service.audit_reservation(
            db, users["teacher_admin"], reservation.id, 1, self_audit=True
        )

    assert exc_info.value.code == 422
    assert exc_info.value.error_code == ReservationErrorCode.SELF_AUDIT_INVALID


def test_teacher_admin_can_audit_other_without_self_audit(db, users, reservation):
    reservation_service.audit_reservation(
        db, users["teacher_admin"], reservation.id, 1
    )
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.APPROVED
    assert reservation.self_audit is False


def test_create_api_writes_submit_history(db, users, lab_equipment, client):
    lab, equipment = lab_equipment
    headers = _login(client, "audit_student")
    headers["X-Request-ID"] = "req-create"

    response = client.post(
        "/api/reservation",
        json=_booking_payload(lab, equipment),
        headers=headers,
    )

    assert response.status_code == 200
    created = db.scalar(select(Reservation))
    history = _history(db, created.id)
    assert len(history) == 1
    assert history[0].action == ReservationAction.SUBMIT
    assert history[0].from_status is None
    assert history[0].to_status == ReservationStatus.PENDING
    assert history[0].actor_id == users["student"].id
    assert history[0].request_id == "req-create"


def test_audit_api_passes_reject_reason_and_request_id(
    db, users, lab_equipment, client
):
    lab, equipment = lab_equipment
    student_headers = _login(client, "audit_student")
    assert client.post(
        "/api/reservation",
        json=_booking_payload(lab, equipment),
        headers=student_headers,
    ).status_code == 200
    reservation = db.scalar(select(Reservation))

    admin_headers = _login(client, "audit_admin")
    admin_headers["X-Request-ID"] = "req-api-reject"
    response = client.put(
        f"/api/reservation/{reservation.id}/audit",
        json={"status": 2, "reject_reason": "设备维护"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    db.expire_all()
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.REJECTED
    assert reservation.reject_reason == "设备维护"
    history = _history(db, reservation.id)
    assert history[-1].request_id == "req-api-reject"
    assert history[-1].action == ReservationAction.REJECT


def test_audit_api_requires_reason(db, users, lab_equipment, client):
    lab, equipment = lab_equipment
    assert client.post(
        "/api/reservation",
        json=_booking_payload(lab, equipment),
        headers=_login(client, "audit_student"),
    ).status_code == 200
    reservation = db.scalar(select(Reservation))

    response = client.put(
        f"/api/reservation/{reservation.id}/audit",
        json={"status": 2},
        headers=_login(client, "audit_admin"),
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == ReservationErrorCode.REJECT_REASON_REQUIRED


def test_self_audit_api(db, users, lab_equipment, client):
    lab, _ = lab_equipment
    headers = _login(client, "audit_teacher_admin")
    assert client.post(
        "/api/reservation",
        json=_booking_payload(lab),
        headers=headers,
    ).status_code == 200
    reservation = db.scalar(select(Reservation))

    without_flag = client.put(
        f"/api/reservation/{reservation.id}/audit",
        json={"status": 1},
        headers=headers,
    )
    assert without_flag.status_code == 403
    assert without_flag.json()["error_code"] == ReservationErrorCode.SELF_AUDIT_REQUIRED

    with_flag = client.put(
        f"/api/reservation/{reservation.id}/audit",
        json={"status": 1, "self_audit": True},
        headers=headers,
    )
    assert with_flag.status_code == 200
    db.expire_all()
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.APPROVED
    assert reservation.self_audit is True