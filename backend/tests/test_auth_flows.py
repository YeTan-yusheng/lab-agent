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
from app.models.process_audit import ActionType, ProcessAudit
from app.models.user import User, UserRoles

PASSWORD_HASH = hash_password("123456")

LOGIN_CASES = [
    (
        "student01",
        ["student"],
        {"book_equipment", "use_ai"},
        "student",
        "学生",
    ),
    (
        "teacher01",
        ["teacher"],
        {"book_equipment", "book_lab", "use_ai"},
        "teacher",
        "教师",
    ),
    (
        "admin01",
        ["admin"],
        {
            "manage_resources",
            "audit_reservation",
            "view_admin_stats",
            "manage_users",
            "manage_kb",
            "use_ai",
        },
        "admin",
        "管理员",
    ),
    (
        "teacher_admin01",
        ["teacher", "admin"],
        {
            "book_equipment",
            "book_lab",
            "manage_resources",
            "audit_reservation",
            "view_admin_stats",
            "manage_users",
            "manage_kb",
            "use_ai",
        },
        "admin",
        "教师/管理员",
    ),
]


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


def _create_user(db, username, roles, *, status=1):
    legacy_role = (
        "admin"
        if "admin" in roles
        else ("teacher" if "teacher" in roles else "student")
    )
    user = User(
        username=username,
        password=PASSWORD_HASH,
        name=username,
        role=legacy_role,
        status=status,
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
    result = {
        username: _create_user(db, username, roles)
        for username, roles, _, _, _ in LOGIN_CASES
    }
    result["roleless01"] = _create_user(db, "roleless01", [])
    result["disabled01"] = _create_user(db, "disabled01", ["student"], status=0)
    result["bad_combo"] = _create_user(
        db, "bad_combo", ["teacher", "student"]
    )
    return result


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


def _login(client, username, password="123456"):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("username", "roles", "capabilities", "primary_role", "display_name"),
    LOGIN_CASES,
)
def test_login_returns_current_user_profile(
    client, users, username, roles, capabilities, primary_role, display_name
):
    response = _login(client, username)

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200

    data = body["data"]
    assert data["token"]
    user = data["user"]
    assert user["roles"] == roles
    assert set(user["capabilities"]) == capabilities
    assert user["primary_role"] == primary_role
    assert user["display_name"] == display_name


def test_me_matches_login_user_payload(client, users):
    login = _login(client, "teacher_admin01")
    login_user = login.json()["data"]["user"]
    token = login.json()["data"]["token"]

    response = client.get("/api/user/me", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json()["code"] == 200
    assert response.json()["data"] == login_user


def test_update_me_keeps_current_user_capabilities(client, users):
    login = _login(client, "student01")
    token = login.json()["data"]["token"]

    response = client.put(
        "/api/user/me",
        json={"name": "新名字"},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    assert response.json()["code"] == 200
    data = response.json()["data"]
    assert data["name"] == "新名字"
    assert data["roles"] == ["student"]
    assert set(data["capabilities"]) == {"book_equipment", "use_ai"}


def test_register_with_roles_still_creates_student(client, db):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "newstudent",
            "password": "123456",
            "name": "新学生",
            "roles": ["admin"],
        },
    )

    assert response.json()["code"] == 200
    user = db.scalar(select(User).where(User.username == "newstudent"))
    assert user is not None
    assert user.role == "student"
    assert set(
        db.scalars(select(UserRoles.role_code).where(UserRoles.user_id == user.id))
    ) == {"student"}

    login = _login(client, "newstudent")
    assert login.json()["code"] == 200
    login_user = login.json()["data"]["user"]
    assert login_user["roles"] == ["student"]
    assert set(login_user["capabilities"]) == {"book_equipment", "use_ai"}

    me = client.get(
        "/api/user/me",
        headers=_bearer(login.json()["data"]["token"]),
    )
    assert me.status_code == 200
    assert me.json()["data"]["roles"] == ["student"]


def test_register_duplicate_username_is_rejected(client, db):
    payload = {"username": "duplicate01", "password": "123456"}
    assert client.post("/api/auth/register", json=payload).json()["code"] == 200

    before = db.scalar(select(func.count()).select_from(User))
    response = client.post("/api/auth/register", json=payload)
    after = db.scalar(select(func.count()).select_from(User))

    assert response.json()["code"] != 200
    assert after == before


def test_password_change_invalidates_old_token(client, db, users):
    login = _login(client, "student01")
    old_token = login.json()["data"]["token"]

    response = client.put(
        "/api/user/password",
        json={"old_password": "123456", "new_password": "654321"},
        headers=_bearer(old_token),
    )

    assert response.json()["code"] == 200

    old_me = client.get("/api/user/me", headers=_bearer(old_token))
    assert old_me.status_code == 401

    old_login = _login(client, "student01", "123456")
    assert old_login.json()["code"] == 401

    new_login = _login(client, "student01", "654321")
    assert new_login.json()["code"] == 200
    new_token = new_login.json()["data"]["token"]
    assert client.get("/api/user/me", headers=_bearer(new_token)).status_code == 200

    user = db.scalar(select(User).where(User.username == "student01"))
    db.refresh(user)
    assert user.token_version == 1


def test_password_change_writes_reset_audit(client, db, users):
    user = users["student01"]
    token = _login(client, "student01").json()["data"]["token"]

    response = client.put(
        "/api/user/password",
        json={"old_password": "123456", "new_password": "654321"},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    db.expire_all()
    audits = db.scalars(
        select(ProcessAudit).where(ProcessAudit.action == ActionType.reset_password)
    ).all()
    assert len(audits) == 1
    audit = audits[0]
    assert audit.actor_user_id == user.id
    assert audit.target_user_id == user.id
    assert audit.result == "success"
    assert audit.request_id
    assert audit.old_roles is None
    assert audit.new_roles is None


def test_disabled_user_cannot_login(client, users):
    response = _login(client, "disabled01")

    assert response.json()["code"] == 401
    assert response.json()["data"] is None


def test_roleless_user_cannot_login(client, users):
    response = _login(client, "roleless01")

    assert response.json()["code"] == 401


def test_invalid_role_combination_cannot_login(client, users):
    response = _login(client, "bad_combo")

    assert response.json()["code"] == 401