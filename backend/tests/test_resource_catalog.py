import datetime
import uuid

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import app as api_router
from app.core.database import get_db
from app.core.exceptions import (
    BusinessException,
    RoleValidationError,
    bussiness_excpetion_hadler,
    http_excpetion_hadler,
    role_validation_exception_handler,
    validation_excpetion_hadler,
)
from app.core.password import hash_password
from app.models.base import Base
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.lab_closed_day import LabClosedDay
from app.models.reservation import Reservation
from app.models.user import User, UserRoles

PASSWORD_HASH = hash_password("123456")
CLOSED_DATE = datetime.date(2099, 12, 31)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False)
    with TestSessionLocal() as session:
        yield session
    engine.dispose()


def _create_user(db, username, roles):
    user = User(
        username=username,
        password=PASSWORD_HASH,
        name=username,
        role="admin" if "admin" in roles else ("teacher" if "teacher" in roles else "student"),
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
        "admin": _create_user(db, "admin", ["admin"]),
        "teacher": _create_user(db, "teacher", ["teacher"]),
        "student": _create_user(db, "student", ["student"]),
    }


@pytest.fixture()
def lab_equipment(db):
    lab = Lab(
        name="基础实验室",
        location="A101",
        capacity=20,
        open_time="08:00",
        close_time="18:00",
        description="基础资源",
        status=1,
    )
    db.add(lab)
    db.flush()
    equipment = Equipment(
        lab_id=lab.id,
        name="基础设备",
        description="基础设备说明",
        spec="S-1",
        quantity=1,
        status=1,
    )
    db.add(equipment)
    db.commit()
    db.refresh(lab)
    db.refresh(equipment)
    return lab, equipment


def _build_app():
    app = FastAPI()
    app.include_router(api_router)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = (
            request.headers.get("X-Request-ID") or uuid.uuid4().hex
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    app.add_exception_handler(BusinessException, bussiness_excpetion_hadler)
    app.add_exception_handler(HTTPException, http_excpetion_hadler)
    app.add_exception_handler(RequestValidationError, validation_excpetion_hadler)
    app.add_exception_handler(RoleValidationError, role_validation_exception_handler)
    return app


@pytest.fixture()
def client(db):
    app = _build_app()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def _login(client, username):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": "123456"},
    )


def _headers(client, username):
    response = _login(client, username)
    assert response.json()["code"] == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def _closed_day_payload(day=CLOSED_DATE, reason="闭馆"):
    return {"date": day.isoformat(), "reason": reason}


# ---------- 实验室 ----------


def test_lab_list_filters_status_zero(client, db, users):
    db.add(Lab(name="关闭实验室", capacity=1, status=0))
    db.commit()

    response = client.get(
        "/api/lab/list",
        params={"status": 0},
        headers=_headers(client, "admin"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["list"][0]["name"] == "关闭实验室"


def test_lab_list_rejects_invalid_pagination(client, users):
    headers = _headers(client, "admin")

    assert client.get("/api/lab/list?page=0", headers=headers).status_code == 422
    assert (
        client.get("/api/lab/list?page_size=101", headers=headers).status_code == 422
    )


def test_lab_detail_contains_closed_days(client, db, users, lab_equipment):
    lab, _ = lab_equipment
    db.add(LabClosedDay(lab_id=lab.id, date=CLOSED_DATE, reason="元旦闭馆"))
    db.commit()

    response = client.get(
        f"/api/lab/{lab.id}", headers=_headers(client, "student")
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == lab.name
    assert data["closed_days"] == [
        {"lab_id": lab.id, "date": "2099-12-31", "reason": "元旦闭馆"}
    ]


def test_lab_detail_returns_404(client, users):
    response = client.get("/api/lab/999999", headers=_headers(client, "student"))
    assert response.status_code == 404


def test_lab_create_duplicate_and_invalid_time(client, users):
    headers = _headers(client, "admin")
    payload = {
        "name": "新实验室",
        "capacity": 10,
        "open_time": "08:00",
        "close_time": "18:00",
        "status": 1,
    }

    assert client.post("/api/lab", json=payload, headers=headers).status_code == 200
    assert client.post("/api/lab", json=payload, headers=headers).status_code == 409

    invalid = {**payload, "name": "非法时间实验室", "open_time": "18:00", "close_time": "08:00"}
    assert client.post("/api/lab", json=invalid, headers=headers).status_code == 422


def test_lab_update_rejects_null_required_and_clears_optional(
    client, db, users, lab_equipment
):
    lab, _ = lab_equipment
    headers = _headers(client, "admin")

    assert (
        client.put(f"/api/lab/{lab.id}", json={"name": None}, headers=headers).status_code
        == 422
    )
    assert (
        client.put(
            f"/api/lab/{lab.id}", json={"capacity": None}, headers=headers
        ).status_code
        == 422
    )

    response = client.put(
        f"/api/lab/{lab.id}", json={"location": None}, headers=headers
    )
    assert response.status_code == 200
    db.refresh(lab)
    assert lab.location is None


def test_lab_update_rejects_null_times_and_invalid_capacity(
    client, users, lab_equipment
):
    lab, _ = lab_equipment
    headers = _headers(client, "admin")

    for payload in (
        {"open_time": None},
        {"close_time": None},
        {"capacity": 0},
    ):
        assert (
            client.put(f"/api/lab/{lab.id}", json=payload, headers=headers).status_code
            == 422
        )


def test_lab_update_rejects_duplicate_name(client, db, users, lab_equipment):
    lab, _ = lab_equipment
    other = Lab(name="第二实验室", capacity=1, status=1)
    db.add(other)
    db.commit()

    response = client.put(
        f"/api/lab/{lab.id}",
        json={"name": other.name},
        headers=_headers(client, "admin"),
    )

    assert response.status_code == 409


def test_lab_delete_rejects_reservation(client, db, users):
    lab = Lab(name="预约实验室", capacity=1, status=1)
    db.add(lab)
    db.flush()
    db.add(
        Reservation(
            user_id=users["student"].id,
            lab_id=lab.id,
            date="2099-01-01",
            start_time="09:00",
            end_time="10:00",
            status=1,
        )
    )
    db.commit()

    response = client.delete(
        f"/api/lab/{lab.id}", headers=_headers(client, "admin")
    )

    assert response.status_code == 409


def test_lab_delete_rejects_equipment_and_cleans_closed_days(
    client, db, users, lab_equipment
):
    lab, _ = lab_equipment
    headers = _headers(client, "admin")

    assert client.delete(f"/api/lab/{lab.id}", headers=headers).status_code == 409

    empty_lab = Lab(name="无设备实验室", capacity=1, status=1)
    db.add(empty_lab)
    db.flush()
    db.add(LabClosedDay(lab_id=empty_lab.id, date=CLOSED_DATE, reason="闭馆"))
    db.commit()

    response = client.delete(f"/api/lab/{empty_lab.id}", headers=headers)
    assert response.status_code == 200
    assert db.get(Lab, empty_lab.id) is None
    assert db.scalar(
        select(func.count()).select_from(LabClosedDay).where(
            LabClosedDay.lab_id == empty_lab.id
        )
    ) == 0


# ---------- 设备 ----------


def test_equipment_list_filters(client, db, users, lab_equipment):
    lab, equipment = lab_equipment
    db.add(
        Equipment(
            lab_id=lab.id,
            name="维修设备",
            quantity=1,
            status=0,
        )
    )
    db.commit()

    response = client.get(
        "/api/equipment/list",
        params={"lab_id": lab.id, "status": 0},
        headers=_headers(client, "student"),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["list"][0]["name"] == "维修设备"


def test_equipment_detail_includes_lab_status(client, users, lab_equipment):
    lab, equipment = lab_equipment

    response = client.get(
        f"/api/equipment/{equipment.id}", headers=_headers(client, "student")
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["lab_name"] == lab.name
    assert data["lab_status"] == 1


def test_equipment_detail_returns_404(client, users):
    response = client.get(
        "/api/equipment/999999", headers=_headers(client, "student")
    )

    assert response.status_code == 404


def test_equipment_create_validation_and_duplicate(client, db, users, lab_equipment):
    lab, equipment = lab_equipment
    headers = _headers(client, "admin")

    assert (
        client.post(
            "/api/equipment",
            json={"lab_id": 999999, "name": "无效实验室设备", "quantity": 1},
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/equipment",
            json={"lab_id": lab.id, "name": equipment.name, "quantity": 1},
            headers=headers,
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/equipment",
            json={"lab_id": lab.id, "name": " ", "quantity": 1},
            headers=headers,
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/equipment",
            json={"lab_id": lab.id, "name": "无效数量", "quantity": 0},
            headers=headers,
        ).status_code
        == 422
    )


def test_equipment_create_allows_same_name_in_other_lab(
    client, db, users, lab_equipment
):
    _, equipment = lab_equipment
    other_lab = Lab(name="另一实验室", capacity=1, status=1)
    db.add(other_lab)
    db.commit()

    response = client.post(
        "/api/equipment",
        json={"lab_id": other_lab.id, "name": equipment.name, "quantity": 1},
        headers=_headers(client, "admin"),
    )

    assert response.status_code == 200
    assert response.json()["data"]["lab_id"] == other_lab.id


def test_equipment_update_rejects_duplicate_name_in_same_lab(
    client, db, users, lab_equipment
):
    lab, equipment = lab_equipment
    other = Equipment(lab_id=lab.id, name="另一设备", quantity=1, status=1)
    db.add(other)
    db.commit()

    response = client.put(
        f"/api/equipment/{equipment.id}",
        json={"name": other.name},
        headers=_headers(client, "admin"),
    )

    assert response.status_code == 409


def test_equipment_update_rejects_invalid_lab_and_nulls(
    client, db, users, lab_equipment
):
    lab, equipment = lab_equipment
    headers = _headers(client, "admin")

    assert (
        client.put(
            f"/api/equipment/{equipment.id}",
            json={"lab_id": 999999},
            headers=headers,
        ).status_code
        == 404
    )
    for payload in (
        {"lab_id": None},
        {"name": None},
        {"quantity": None},
        {"status": None},
    ):
        assert (
            client.put(
                f"/api/equipment/{equipment.id}", json=payload, headers=headers
            ).status_code
            == 422
        )

    response = client.put(
        f"/api/equipment/{equipment.id}",
        json={"description": None},
        headers=headers,
    )
    assert response.status_code == 200
    db.refresh(equipment)
    assert equipment.description is None


def test_equipment_update_rejects_empty_name(client, users, lab_equipment):
    _, equipment = lab_equipment

    response = client.put(
        f"/api/equipment/{equipment.id}",
        json={"name": ""},
        headers=_headers(client, "admin"),
    )

    assert response.status_code == 422


def test_equipment_delete_rejects_reservation(client, db, users, lab_equipment):
    lab, equipment = lab_equipment
    db.add(
        Reservation(
            user_id=users["student"].id,
            lab_id=lab.id,
            equipment_id=equipment.id,
            date="2099-01-01",
            start_time="09:00",
            end_time="10:00",
            status=0,
        )
    )
    db.commit()

    response = client.delete(
        f"/api/equipment/{equipment.id}", headers=_headers(client, "admin")
    )

    assert response.status_code == 409


# ---------- 闭馆日 ----------


def test_closed_day_upsert_and_list(client, db, users, lab_equipment):
    lab, _ = lab_equipment
    headers = _headers(client, "admin")

    assert (
        client.get(
            f"/api/lab/{lab.id}/closed_days", headers=headers
        ).json()["data"]
        == []
    )

    assert (
        client.put(
            f"/api/lab/{lab.id}/closed_day",
            json=_closed_day_payload(reason="第一次"),
            headers=headers,
        ).status_code
        == 200
    )
    response = client.put(
        f"/api/lab/{lab.id}/closed_day",
        json=_closed_day_payload(reason="第二次"),
        headers=headers,
    )
    assert response.status_code == 200

    data = client.get(
        f"/api/lab/{lab.id}/closed_days", headers=headers
    ).json()["data"]
    assert len(data) == 1
    assert data[0]["date"] == "2099-12-31"
    assert data[0]["reason"] == "第二次"


def test_closed_day_requires_existing_lab(client, users):
    headers = _headers(client, "admin")

    assert (
        client.get("/api/lab/999999/closed_days", headers=headers).status_code == 404
    )
    assert (
        client.put(
            "/api/lab/999999/closed_day",
            json=_closed_day_payload(),
            headers=headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(
            "/api/lab/999999/closed_days",
            params={"date": CLOSED_DATE.isoformat()},
            headers=headers,
        ).status_code
        == 404
    )


def test_closed_day_delete_rejects_past_date(client, users, lab_equipment):
    lab, _ = lab_equipment

    response = client.delete(
        f"/api/lab/{lab.id}/closed_days",
        params={"date": "2000-01-01"},
        headers=_headers(client, "admin"),
    )

    assert response.status_code == 422


def test_closed_day_rejects_past_and_invalid_date(client, users, lab_equipment):
    lab, _ = lab_equipment
    headers = _headers(client, "admin")

    past = client.put(
        f"/api/lab/{lab.id}/closed_day",
        json={"date": "2000-01-01", "reason": "过去"},
        headers=headers,
    )
    invalid = client.put(
        f"/api/lab/{lab.id}/closed_day",
        json={"date": "2099-02-31", "reason": "非法"},
        headers=headers,
    )

    assert past.status_code == 422
    assert invalid.status_code == 422


def test_closed_day_delete(client, users, lab_equipment):
    lab, _ = lab_equipment
    headers = _headers(client, "admin")

    client.put(
        f"/api/lab/{lab.id}/closed_day",
        json=_closed_day_payload(),
        headers=headers,
    )

    assert (
        client.delete(
            f"/api/lab/{lab.id}/closed_days",
            params={"date": CLOSED_DATE.isoformat()},
            headers=headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/lab/{lab.id}/closed_days", headers=headers
        ).json()["data"]
        == []
    )
    assert (
        client.delete(
            f"/api/lab/{lab.id}/closed_days",
            params={"date": CLOSED_DATE.isoformat()},
            headers=headers,
        ).status_code
        == 404
    )


# ---------- 权限 ----------


def test_write_requires_manage_resources(client, users, lab_equipment):
    lab, equipment = lab_equipment
    student_headers = _headers(client, "student")

    assert (
        client.post(
            "/api/lab",
            json={"name": "学生不能建", "capacity": 1, "status": 1},
            headers=student_headers,
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/lab/{lab.id}", json={"capacity": 2}, headers=student_headers
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/lab/{lab.id}", headers=student_headers).status_code
        == 403
    )
    assert (
        client.post(
            "/api/equipment",
            json={"lab_id": lab.id, "name": "学生不能建", "quantity": 1},
            headers=student_headers,
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/equipment/{equipment.id}",
            json={"quantity": 2},
            headers=student_headers,
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/equipment/{equipment.id}", headers=student_headers
        ).status_code
        == 403
    )


def test_read_requires_login(client, users, lab_equipment):
    lab, _ = lab_equipment

    assert client.get("/api/lab/list").status_code == 401
    assert client.get(f"/api/lab/{lab.id}").status_code == 401
    assert client.get("/api/equipment/list").status_code == 401