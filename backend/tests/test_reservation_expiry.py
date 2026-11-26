from datetime import datetime, timedelta
import asyncio

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
    ReservationStatus,
)
from app.core.reservation_rules import OCCUPYING_STATUSES
from app.models.base import Base
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.reservation import Reservation
from app.models.reservation_status_history import ReservationStatusHistory
from app.models.user import User, UserRoles
from app.schemas.reservation import AvailabilityRequest
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
        "student": _create_user(db, "expiry_student", ["student"]),
        "teacher": _create_user(db, "expiry_teacher", ["teacher"]),
        "admin": _create_user(db, "expiry_admin", ["admin"]),
        "teacher_admin": _create_user(
            db, "expiry_teacher_admin", ["teacher", "admin"]
        ),
    }


@pytest.fixture()
def lab(db):
    item = Lab(
        name="过期测试实验室",
        location="D401",
        capacity=10,
        open_time="08:00",
        close_time="18:00",
        status=1,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _create_reservation(
    db,
    user_id,
    lab_id,
    *,
    date_value,
    start_time="10:00",
    end_time="11:00",
    status=ReservationStatus.PENDING,
):
    item = Reservation(
        user_id=user_id,
        lab_id=lab_id,
        date=date_value,
        start_time=start_time,
        end_time=end_time,
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


def test_expire_pending_in_past_day(db, users, lab):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db, users["student"].id, lab.id, date_value="2026-11-23"
    )

    changed = reservation_service.expire_pending_reservations(db, now=now)
    db.refresh(reservation)

    assert changed == 1
    assert reservation.status == ReservationStatus.EXPIRED
    history = _history(db, reservation.id)
    assert len(history) == 1
    assert history[0].action == ReservationAction.EXPIRE
    assert history[0].from_status == ReservationStatus.PENDING
    assert history[0].to_status == ReservationStatus.EXPIRED
    assert history[0].actor_id is None
    assert history[0].reason == "待审核超时"
    assert history[0].request_id.startswith("system:expire:")


@pytest.mark.parametrize(
    ("start_time", "expected_status"),
    [
        ("09:59", ReservationStatus.EXPIRED),
        ("10:00", ReservationStatus.EXPIRED),
        ("10:01", ReservationStatus.PENDING),
    ],
)
def test_expire_today_boundary(db, users, lab, start_time, expected_status):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-24",
        start_time=start_time,
        end_time="11:00",
    )

    reservation_service.expire_pending_reservations(db, now=now)
    db.refresh(reservation)
    assert reservation.status == expected_status


def test_expire_ignores_future_and_non_pending(db, users, lab):
    now = datetime(2026, 11, 24, 10, 0)
    future = _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-25",
    )
    approved = _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-23",
        status=ReservationStatus.APPROVED,
    )
    rejected = _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-23",
        status=ReservationStatus.REJECTED,
    )
    cancelled = _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-23",
        status=ReservationStatus.CANCELLED,
    )

    changed = reservation_service.expire_pending_reservations(db, now=now)

    assert changed == 0
    for item, status in (
        (future, ReservationStatus.PENDING),
        (approved, ReservationStatus.APPROVED),
        (rejected, ReservationStatus.REJECTED),
        (cancelled, ReservationStatus.CANCELLED),
    ):
        db.refresh(item)
        assert item.status == status
        assert _history(db, item.id) == []


def test_expire_is_idempotent_and_releases_conflict(db, users, lab):
    now = datetime(2026, 11, 24, 10, 0)
    reservation = _create_reservation(
        db, users["student"].id, lab.id, date_value="2026-11-23"
    )

    assert reservation_service.expire_pending_reservations(db, now=now) == 1
    assert reservation_service.expire_pending_reservations(db, now=now) == 0
    db.refresh(reservation)
    assert reservation.status == ReservationStatus.EXPIRED
    assert len(_history(db, reservation.id)) == 1

    result = reservation_service.find_conflicts(
        db,
        AvailabilityRequest(
            lab_id=lab.id,
            date="2026-11-23",
            start_time="10:00",
            end_time="11:00",
        ),
    )
    assert result.available is True


def test_expired_status_is_not_occupying(db, users, lab):
    reservation = _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-23",
        status=ReservationStatus.EXPIRED,
    )

    occupying = db.scalar(
        select(Reservation).where(
            Reservation.id == reservation.id,
            Reservation.status.in_(OCCUPYING_STATUSES),
        )
    )
    assert occupying is None


def test_expire_batches_until_done(db, users, lab):
    now = datetime(2026, 11, 24, 10, 0)
    reservations = [
        _create_reservation(
            db, users["student"].id, lab.id, date_value="2026-11-23"
        )
        for _ in range(2)
    ]

    changed = reservation_service.expire_pending_reservations(
        db, now=now, batch_size=1
    )

    assert changed == 2
    for reservation in reservations:
        db.refresh(reservation)
        assert reservation.status == ReservationStatus.EXPIRED
        assert len(_history(db, reservation.id)) == 1


def test_run_expire_scan_continues_after_error(monkeypatch):
    calls = []

    def fake_expire():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("模拟数据库异常")

    async def fake_sleep(_seconds):
        if len(calls) >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(
        reservation_service, "expire_pending_reservations", fake_expire
    )
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(reservation_service.run_expire_scan())

    assert len(calls) == 2


def test_list_admin_default_excludes_cancelled_and_expired(db, users, lab):
    pending = _create_reservation(
        db, users["student"].id, lab.id, date_value="2026-11-25"
    )
    approved = _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-25",
        status=ReservationStatus.APPROVED,
    )
    rejected = _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-25",
        status=ReservationStatus.REJECTED,
    )
    cancelled = _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-25",
        status=ReservationStatus.CANCELLED,
    )
    expired = _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-25",
        status=ReservationStatus.EXPIRED,
    )

    page = reservation_service.get_reservation_page_list(
        db, users["admin"], 1, 10
    )
    ids = {item.id for item in page.list}
    assert ids == {pending.id, approved.id, rejected.id}

    expired_page = reservation_service.get_reservation_page_list(
        db, users["admin"], 1, 10, status=ReservationStatus.EXPIRED
    )
    assert [item.id for item in expired_page.list] == [expired.id]

    cancelled_page = reservation_service.get_reservation_page_list(
        db, users["admin"], 1, 10, status=ReservationStatus.CANCELLED
    )
    assert [item.id for item in cancelled_page.list] == [cancelled.id]


def test_list_owner_sees_all_own_and_filters(db, users, lab):
    own = _create_reservation(
        db, users["student"].id, lab.id, date_value="2026-11-25"
    )
    other = _create_reservation(
        db, users["teacher"].id, lab.id, date_value="2026-11-26"
    )

    page = reservation_service.get_reservation_page_list(
        db, users["student"], 1, 10
    )
    assert [item.id for item in page.list] == [own.id]

    filtered = reservation_service.get_reservation_page_list(
        db,
        users["admin"],
        1,
        10,
        lab_id=lab.id,
        date_from="2026-11-26",
        date_to="2026-11-26",
    )
    assert [item.id for item in filtered.list] == [other.id]


def test_my_list_for_teacher_admin_only_returns_own(db, users, lab):
    own = _create_reservation(
        db, users["teacher_admin"].id, lab.id, date_value="2026-11-25"
    )
    other = _create_reservation(
        db, users["student"].id, lab.id, date_value="2026-11-25"
    )

    mine_page = reservation_service.get_reservation_page_list(
        db, users["teacher_admin"], 1, 10, mine=True
    )
    assert [item.id for item in mine_page.list] == [own.id]

    audit_page = reservation_service.get_reservation_page_list(
        db, users["teacher_admin"], 1, 10
    )
    assert {item.id for item in audit_page.list} == {own.id, other.id}


def test_list_invalid_date_filters_raise_422(db, users):
    with pytest.raises(BusinessException) as exc_info:
        reservation_service.get_reservation_page_list(
            db, users["admin"], 1, 10, date_from="bad"
        )
    assert exc_info.value.code == 422

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.get_reservation_page_list(
            db,
            users["admin"],
            1,
            10,
            date_from="2026-11-26",
            date_to="2026-11-25",
        )
    assert exc_info.value.code == 422


def test_pending_count_requires_audit_capability(db, users, lab):
    _create_reservation(db, users["student"].id, lab.id, date_value="2026-11-25")
    _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-25",
        status=ReservationStatus.APPROVED,
    )

    assert reservation_service.get_audit_pending_count(db, users["admin"]) == 1

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.get_audit_pending_count(db, users["student"])
    assert exc_info.value.code == 403


def test_history_permissions_order_and_actor_name(db, users, lab):
    reservation = _create_reservation(
        db, users["student"].id, lab.id, date_value="2026-11-25"
    )
    db.add_all(
        [
            ReservationStatusHistory(
                reservation_id=reservation.id,
                from_status=None,
                to_status=ReservationStatus.PENDING,
                action=ReservationAction.SUBMIT,
                actor_id=users["student"].id,
                request_id="req-submit",
            ),
            ReservationStatusHistory(
                reservation_id=reservation.id,
                from_status=ReservationStatus.PENDING,
                to_status=ReservationStatus.APPROVED,
                action=ReservationAction.APPROVE,
                actor_id=users["admin"].id,
                request_id="req-approve",
            ),
        ]
    )
    db.commit()

    owner_history = reservation_service.get_reservation_history(
        db, users["student"], reservation.id
    )
    assert [item.action for item in owner_history] == ["submit", "approve"]
    assert owner_history[0].actor_name == users["student"].name
    assert owner_history[1].actor_name == users["admin"].name

    admin_history = reservation_service.get_reservation_history(
        db, users["admin"], reservation.id
    )
    assert len(admin_history) == 2

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.get_reservation_history(
            db, users["teacher"], reservation.id
        )
    assert exc_info.value.code == 403

    with pytest.raises(BusinessException) as exc_info:
        reservation_service.get_reservation_history(db, users["admin"], 999999)
    assert exc_info.value.code == 404


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


def test_list_api_filters_and_pending_count(db, users, lab, client):
    expired = _create_reservation(
        db,
        users["student"].id,
        lab.id,
        date_value="2026-11-25",
        status=ReservationStatus.EXPIRED,
    )
    pending = _create_reservation(
        db, users["student"].id, lab.id, date_value="2026-11-25"
    )

    admin_headers = _login(client, "expiry_admin")
    expired_response = client.get(
        "/api/reservation/list?status=4", headers=admin_headers
    )
    assert expired_response.status_code == 200
    assert [row["id"] for row in expired_response.json()["data"]["list"]] == [
        expired.id
    ]

    count_response = client.get(
        "/api/reservation/audit/pending-count", headers=admin_headers
    )
    assert count_response.status_code == 200
    assert count_response.json()["data"]["count"] == 1

    student_headers = _login(client, "expiry_student")
    forbidden = client.get(
        "/api/reservation/audit/pending-count", headers=student_headers
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error_code"] == "RESERVATION_FORBIDDEN"


def test_my_list_api_for_teacher_admin_only_returns_own(db, users, lab, client):
    own = _create_reservation(
        db, users["teacher_admin"].id, lab.id, date_value="2026-11-25"
    )
    _create_reservation(
        db, users["student"].id, lab.id, date_value="2026-11-25"
    )

    response = client.get(
        "/api/reservation/list?mine=true",
        headers=_login(client, "expiry_teacher_admin"),
    )

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]["list"]] == [own.id]


def test_history_api_owner_and_non_owner(db, users, lab, client):
    reservation = _create_reservation(
        db, users["student"].id, lab.id, date_value="2026-11-25"
    )
    db.add(
        ReservationStatusHistory(
            reservation_id=reservation.id,
            from_status=None,
            to_status=ReservationStatus.PENDING,
            action=ReservationAction.SUBMIT,
            actor_id=users["student"].id,
            request_id="req-api-history",
        )
    )
    db.commit()

    owner = client.get(
        f"/api/reservation/{reservation.id}/history",
        headers=_login(client, "expiry_student"),
    )
    assert owner.status_code == 200
    assert owner.json()["data"][0]["action"] == "submit"
    assert owner.json()["data"][0]["request_id"] == "req-api-history"

    other = client.get(
        f"/api/reservation/{reservation.id}/history",
        headers=_login(client, "expiry_teacher"),
    )
    assert other.status_code == 403