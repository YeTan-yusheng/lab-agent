import uuid

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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
from app.models.reservation import Reservation
from app.models.user import User, UserRoles

PASSWORD_HASH = hash_password("123456")


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
        "student": _create_user(db, "res_student", ["student"]),
        "teacher": _create_user(db, "res_teacher", ["teacher"]),
        "admin": _create_user(db, "res_admin", ["admin"]),
        "teacher_admin": _create_user(db, "res_teacher_admin", ["teacher", "admin"]),
    }


@pytest.fixture()
def lab_equipment(db):
    lab = Lab(
        name="预约权限实验室",
        location="B201",
        capacity=20,
        open_time="08:00",
        close_time="18:00",
        status=1,
    )
    db.add(lab)
    db.flush()
    equipment = Equipment(
        lab_id=lab.id,
        name="预约权限设备",
        spec="P-1",
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


def _booking_payload(lab, equipment=None):
    payload = {
        "lab_id": lab.id,
        "date": "2099-01-01",
        "start_time": "10:00",
        "end_time": "11:00",
    }
    if equipment is not None:
        payload["equipment_id"] = equipment.id
    return payload


def test_student_can_book_equipment(client, users, lab_equipment):
    lab, equipment = lab_equipment

    response = client.post(
        "/api/reservation",
        json=_booking_payload(lab, equipment),
        headers=_headers(client, "res_student"),
    )

    assert response.status_code == 200
    assert response.json()["code"] == 200


def test_student_cannot_book_lab(client, users, lab_equipment):
    lab, _ = lab_equipment

    response = client.post(
        "/api/reservation",
        json=_booking_payload(lab),
        headers=_headers(client, "res_student"),
    )

    assert response.status_code == 403


def test_teacher_can_book_lab_and_equipment(client, users, lab_equipment):
    lab, equipment = lab_equipment
    headers = _headers(client, "res_teacher")

    lab_response = client.post(
        "/api/reservation",
        json=_booking_payload(lab),
        headers=headers,
    )
    equipment_response = client.post(
        "/api/reservation",
        json=_booking_payload(lab, equipment),
        headers=headers,
    )

    assert lab_response.status_code == 200
    assert equipment_response.status_code == 200


def test_admin_cannot_book_any_resource(client, users, lab_equipment):
    lab, equipment = lab_equipment
    headers = _headers(client, "res_admin")

    lab_response = client.post(
        "/api/reservation",
        json=_booking_payload(lab),
        headers=headers,
    )
    equipment_response = client.post(
        "/api/reservation",
        json=_booking_payload(lab, equipment),
        headers=headers,
    )

    assert lab_response.status_code == 403
    assert equipment_response.status_code == 403


def test_teacher_admin_can_book_lab_and_equipment(client, users, lab_equipment):
    lab, equipment = lab_equipment
    headers = _headers(client, "res_teacher_admin")

    lab_response = client.post(
        "/api/reservation",
        json=_booking_payload(lab),
        headers=headers,
    )
    equipment_response = client.post(
        "/api/reservation",
        json=_booking_payload(lab, equipment),
        headers=headers,
    )

    assert lab_response.status_code == 200
    assert equipment_response.status_code == 200


def test_only_auditor_can_audit_reservation(client, db, users, lab_equipment):
    lab, equipment = lab_equipment
    student_headers = _headers(client, "res_student")

    client.post(
        "/api/reservation",
        json=_booking_payload(lab, equipment),
        headers=student_headers,
    )
    reservation = db.scalar(select(Reservation))
    assert reservation is not None

    teacher_response = client.put(
        f"/api/reservation/{reservation.id}/audit",
        json={"status": 1},
        headers=_headers(client, "res_teacher"),
    )
    admin_response = client.put(
        f"/api/reservation/{reservation.id}/audit",
        json={"status": 1},
        headers=_headers(client, "res_admin"),
    )

    assert teacher_response.status_code == 403
    assert admin_response.status_code == 200