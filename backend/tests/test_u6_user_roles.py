import uuid
from types import SimpleNamespace

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
from app.core.permissions import validate_roles
from app.models.base import Base
from app.models.user import User, UserRoles
from app.schemas.user import UserUpdateRequest, RolesUpdateRequest
from app.services.user_service import (
    delete_user,
    ensure_not_last_admin,
    update_user,
    update_user_roles,
)

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
    return {
        "admin1": _create_user(db, "admin1", ["admin"]),
        "teacher1": _create_user(db, "teacher1", ["teacher"]),
        "student1": _create_user(db, "student1", ["student"]),
        "target1": _create_user(db, "target1", ["student"]),
    }


@pytest.fixture()
def fake_request():
    return SimpleNamespace(state=SimpleNamespace(request_id="req-test-u6"))


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


def _roles_of(db, user_id):
    return set(
        db.scalars(select(UserRoles.role_code).where(UserRoles.user_id == user_id))
    )


def _admin_headers(client, users):
    response = _login(client, "admin1")
    return _bearer(response.json()["data"]["token"])


def test_admin_can_create_user_with_roles(client, db, users):
    response = client.post(
        "/api/user",
        json={
            "username": "newteacher",
            "password": "123456",
            "name": "新教师",
            "roles": ["teacher"],
        },
        headers=_admin_headers(client, users),
    )

    assert response.json()["code"] == 200
    user = db.scalar(select(User).where(User.username == "newteacher"))
    assert user is not None
    assert _roles_of(db, user.id) == {"teacher"}
    assert user.role == "teacher"

    login = _login(client, "newteacher")
    assert login.json()["code"] == 200
    assert set(login.json()["data"]["user"]["capabilities"]) == {
        "book_equipment",
        "book_lab",
        "use_ai",
    }


@pytest.mark.parametrize("username", ["teacher1", "student1"])
def test_non_admin_cannot_manage_users(client, users, username):
    token = _login(client, username).json()["data"]["token"]
    headers = _bearer(token)
    target_id = users["target1"].id

    assert client.get("/api/user/list", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/user",
            json={"username": "forbidden", "roles": ["student"]},
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/user/{target_id}/roles",
            json={"roles": ["teacher"]},
            headers=headers,
        ).status_code
        == 403
    )
    assert client.delete(f"/api/user/{target_id}", headers=headers).status_code == 403


def test_create_user_with_invalid_role_combination_is_rejected(client, db, users):
    response = client.post(
        "/api/user",
        json={
            "username": "badcombo",
            "roles": ["admin", "student"],
        },
        headers=_admin_headers(client, users),
    )

    assert response.status_code == 422
    assert db.scalar(select(User).where(User.username == "badcombo")) is None


def test_role_update_changes_permissions_and_invalidates_old_token(client, db, users):
    target = users["target1"]
    old_login = _login(client, "target1")
    old_token = old_login.json()["data"]["token"]

    response = client.put(
        f"/api/user/{target.id}/roles",
        json={"roles": ["teacher"]},
        headers=_admin_headers(client, users),
    )

    assert response.json()["code"] == 200
    assert _roles_of(db, target.id) == {"teacher"}
    assert client.get("/api/user/me", headers=_bearer(old_token)).status_code == 401

    new_login = _login(client, "target1")
    assert new_login.json()["code"] == 200
    assert set(new_login.json()["data"]["user"]["capabilities"]) == {
        "book_equipment",
        "book_lab",
        "use_ai",
    }
    db.refresh(target)
    assert target.token_version == 1


@pytest.mark.parametrize("roles", [["teacher"], ["teacher", "admin"]])
def test_user_cannot_change_own_roles(client, db, users, roles):
    admin = users["admin1"]
    before = _roles_of(db, admin.id)

    response = client.put(
        f"/api/user/{admin.id}/roles",
        json={"roles": roles},
        headers=_admin_headers(client, users),
    )

    assert response.json()["code"] != 200
    assert _roles_of(db, admin.id) == before


def test_ensure_not_last_admin_rejects_removing_last_admin(db, users):
    admin = users["admin1"]

    with pytest.raises(BusinessException):
        ensure_not_last_admin(db, admin.id, validate_roles(["teacher"]))


def test_disable_last_admin_is_rejected(db, users, fake_request):
    admin = users["admin1"]

    with pytest.raises(BusinessException):
        update_user(
            fake_request,
            db,
            admin.id,
            UserUpdateRequest(status=0),
            admin,
        )

    db.refresh(admin)
    assert admin.status == 1


def test_delete_last_admin_is_rejected(db, users, fake_request):
    admin = users["admin1"]
    actor = users["teacher1"]

    with pytest.raises(BusinessException):
        delete_user(fake_request, db, admin.id, actor)

    assert db.get(User, admin.id) is not None


def test_admin_profile_update_keeps_target_token_valid(client, db, users):
    target = users["target1"]
    old_token = _login(client, "target1").json()["data"]["token"]

    response = client.put(
        f"/api/user/{target.id}",
        json={"name": "新名字"},
        headers=_admin_headers(client, users),
    )

    assert response.json()["code"] == 200
    assert client.get("/api/user/me", headers=_bearer(old_token)).status_code == 200
    db.refresh(target)
    assert target.token_version == 0


def test_admin_disable_target_invalidates_token(client, db, users):
    target = users["target1"]
    old_token = _login(client, "target1").json()["data"]["token"]

    response = client.put(
        f"/api/user/{target.id}",
        json={"status": 0},
        headers=_admin_headers(client, users),
    )

    assert response.json()["code"] == 200
    assert client.get("/api/user/me", headers=_bearer(old_token)).status_code == 401


def test_user_list_returns_base_fields_only(client, users):
    response = client.get("/api/user/list", headers=_admin_headers(client, users))

    assert response.json()["code"] == 200
    item = response.json()["data"]["list"][0]
    assert "roles" not in item
    assert "capabilities" not in item
    assert "password" not in item
    assert "token_version" not in item




def test_update_user_roles_service_respects_self_rule(db, users, fake_request):
    admin = users["admin1"]

    with pytest.raises(BusinessException):
        update_user_roles(
            fake_request,
            db,
            admin,
            admin.id,
            RolesUpdateRequest(roles=["teacher", "admin"]),
        )


def test_create_user_role_rows_are_unique(db, users):
    admin = users["admin1"]
    assert (
        db.scalar(
            select(func.count())
            .select_from(UserRoles)
            .where(UserRoles.user_id == admin.id)
        )
        == 1
    )


def test_admin_can_get_user_detail_with_roles(client, db, users):
    target = _create_user(db, "teacher_admin_detail", ["teacher", "admin"])

    response = client.get(
        f"/api/user/{target.id}",
        headers=_admin_headers(client, users),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["roles"] == ["teacher", "admin"]
    assert data["display_name"] == "教师/管理员"
    assert "capabilities" not in data
    assert "password" not in data


def test_non_admin_cannot_get_user_detail(client, users):
    target = users["target1"]
    token = _login(client, "teacher1").json()["data"]["token"]

    response = client.get(
        f"/api/user/{target.id}",
        headers=_bearer(token),
    )

    assert response.status_code == 403


def test_get_user_detail_returns_404_for_unknown_user(client, users):
    response = client.get(
        "/api/user/999999",
        headers=_admin_headers(client, users),
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404
