import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import app as api_router
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestContextMiddleware
from app.core.password import hash_password
from app.models import (
    Lab,
    Reservation,
    ReservationStatusHistory,
    User,
    UserRoles,
)
from app.models.base import Base


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


@pytest.fixture()
def client(db):
    app = FastAPI()
    app.include_router(api_router)
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def _user(db, username, roles):
    user = User(
        username=username,
        password=hash_password("123456"),
        name=username,
        role="admin" if "admin" in roles else "student",
        status=1,
    )
    db.add(user)
    db.flush()
    for role_code in roles:
        db.add(UserRoles(user_id=user.id, role_code=role_code))
    db.commit()
    db.refresh(user)
    return user


def _lab(db):
    lab = Lab(
        name="审计实验室",
        location="C301",
        capacity=10,
        open_time="08:00",
        close_time="18:00",
        status=1,
    )
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return lab


def _reservation(db, user, lab, *, date="2099-01-01", status=1):
    reservation = Reservation(
        user_id=user.id,
        lab_id=lab.id,
        date=date,
        start_time="09:00",
        end_time="10:00",
        remark="不应该出现在审计响应里",
        status=status,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def _history(db, reservation, *, action, from_status, to_status, actor, reason=None, request_id):
    item = ReservationStatusHistory(
        reservation_id=reservation.id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor.id if actor else None,
        reason=reason,
        request_id=request_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _login(client, username):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "123456"},
    )
    assert response.json()["code"] == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


@pytest.fixture()
def data(db):
    admin = _user(db, "audit_history_admin", ["admin"])
    student = _user(db, "audit_history_student", ["student"])
    lab = _lab(db)
    first = _reservation(db, student, lab)
    second = _reservation(db, student, lab, date="2099-02-01")
    _history(
        db,
        first,
        action="submit",
        from_status=None,
        to_status=0,
        actor=student,
        request_id="req-submit",
    )
    _history(
        db,
        first,
        action="approve",
        from_status=0,
        to_status=1,
        actor=admin,
        request_id="req-approve",
    )
    _history(
        db,
        second,
        action="reject",
        from_status=0,
        to_status=2,
        actor=admin,
        reason="设备维护",
        request_id="req-reject",
    )
    return {
        "admin": admin,
        "student": student,
        "first": first,
        "second": second,
    }


def test_audit_history_requires_audit_capability(client, data):
    response = client.get(
        "/api/reservation/audit/history",
        headers=_login(client, "audit_history_student"),
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "RESERVATION_FORBIDDEN"


def test_audit_history_returns_context_and_desc_order(client, data):
    response = client.get(
        "/api/reservation/audit/history",
        headers=_login(client, "audit_history_admin"),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["data"]["total"] == 3
    items = payload["data"]["list"]
    assert [item["action"] for item in items] == ["reject", "approve", "submit"]
    reject = items[0]
    assert reject["owner_name"] == "audit_history_student"
    assert reject["lab_name"] == "审计实验室"
    assert reject["date"] == "2099-02-01"
    assert reject["start_time"] == "09:00"
    assert reject["end_time"] == "10:00"
    assert reject["reason"] == "设备维护"
    assert reject["actor_name"] == "audit_history_admin"
    assert reject["request_id"] == "req-reject"
    assert "remark" not in reject


def test_audit_history_filters(client, data):
    headers = _login(client, "audit_history_admin")
    student = data["student"]

    by_reservation = client.get(
        f"/api/reservation/audit/history?reservation_id={data['first'].id}",
        headers=headers,
    ).json()["data"]
    assert by_reservation["total"] == 2
    assert {item["action"] for item in by_reservation["list"]} == {
        "submit",
        "approve",
    }

    by_action = client.get(
        "/api/reservation/audit/history?action=reject",
        headers=headers,
    ).json()["data"]
    assert by_action["total"] == 1
    assert by_action["list"][0]["action"] == "reject"

    by_user = client.get(
        f"/api/reservation/audit/history?user_id={student.id}",
        headers=headers,
    ).json()["data"]
    assert by_user["total"] == 3

    by_date = client.get(
        "/api/reservation/audit/history?date_from=2099-02-01&date_to=2099-02-01",
        headers=headers,
    ).json()["data"]
    assert by_date["total"] == 1
    assert by_date["list"][0]["reservation_id"] == data["second"].id


def test_audit_history_paginates(client, data):
    response = client.get(
        "/api/reservation/audit/history?page=1&page_size=1",
        headers=_login(client, "audit_history_admin"),
    )
    payload = response.json()["data"]

    assert payload["total"] == 3
    assert len(payload["list"]) == 1


def test_audit_history_rejects_invalid_filters(client, data):
    headers = _login(client, "audit_history_admin")

    invalid_action = client.get(
        "/api/reservation/audit/history?action=unknown",
        headers=headers,
    )
    assert invalid_action.status_code == 422

    invalid_range = client.get(
        "/api/reservation/audit/history?date_from=2099-02-02&date_to=2099-02-01",
        headers=headers,
    )
    assert invalid_range.status_code == 422

    invalid_date = client.get(
        "/api/reservation/audit/history?date_from=not-a-date",
        headers=headers,
    )
    assert invalid_date.status_code == 422