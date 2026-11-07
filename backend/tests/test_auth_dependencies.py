from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.database import get_db
from app.core.exceptions import http_excpetion_hadler
from app.core.jwt import create_access_token, decode_access_token
from app.core.password import hash_password
from app.core.permissions import Capability, validate_roles
from app.dependencies.auth import (
    get_current_user,
    require_booking_capability,
    require_capability,
)
from app.models.base import Base
from app.models.user import User, UserRoles
from app.schemas.auth import LoginRequest
from app.services.auth_service import verify_login

ROLE_USERS = {
    "student01": ["student"],
    "teacher01": ["teacher"],
    "admin01": ["admin"],
    "teacher_admin01": ["teacher", "admin"],
}

EXPECTED_CAPABILITIES = {
    "student01": {"book_equipment", "use_ai"},
    "teacher01": {"book_equipment", "book_lab", "use_ai"},
    "admin01": {
        "manage_resources",
        "audit_reservation",
        "view_admin_stats",
        "manage_users",
        "manage_kb",
        "use_ai",
    },
    "teacher_admin01": {
        "book_equipment",
        "book_lab",
        "manage_resources",
        "audit_reservation",
        "view_admin_stats",
        "manage_users",
        "manage_kb",
        "use_ai",
    },
}

PASSWORD_HASH = hash_password("123456")

BOOKING_CASES = [
    ("student01", None, 403),
    ("student01", 101, 200),
    ("teacher01", None, 200),
    ("teacher01", 101, 200),
    ("admin01", None, 403),
    ("admin01", 101, 403),
    ("teacher_admin01", None, 200),
    ("teacher_admin01", 101, 200),
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


def _create_user(db, username, roles, *, status=1, token_version=1):
    profile = validate_roles(roles)
    user = User(
        username=username,
        password=PASSWORD_HASH,
        name=username,
        role=profile.primary_role.value,
        status=status,
        token_version=token_version,
    )
    user.roles = [UserRoles(role_code=role.value) for role in profile.roles]
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def users(db):
    result = {
        username: _create_user(db, username, roles)
        for username, roles in ROLE_USERS.items()
    }
    result["zero_version"] = _create_user(
        db, "zero_version", ["student"], token_version=0
    )
    result["disabled01"] = _create_user(db, "disabled01", ["student"], status=0)
    return result


def _capability_endpoint(capability: Capability):
    def endpoint(current_user: User = Depends(require_capability(capability))):
        return {"capability": capability.value}

    return endpoint


def _build_app():
    app = FastAPI()
    app.add_exception_handler(HTTPException, http_excpetion_hadler)

    @app.get("/_test/me")
    def me(current_user: User = Depends(get_current_user)):
        return {"user_id": current_user.id}

    @app.get("/_test/profile")
    def profile(request: Request, current_user: User = Depends(get_current_user)):
        return request.state.role_profile.to_api()

    @app.get("/_test/management")
    def management(
        current_user: User = Depends(require_capability(Capability.manage_users)),
    ):
        return {"user_id": current_user.id}

    @app.post("/_test/booking")
    def booking(current_user: User = Depends(require_booking_capability)):
        return {"user_id": current_user.id}

    for capability in Capability:
        app.add_api_route(
            f"/_test/capability/{capability.value}",
            _capability_endpoint(capability),
            methods=["GET"],
        )

    return app


@pytest.fixture()
def client(db):
    app = _build_app()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def _encode(payload, key=None):
    return jwt.encode(
        payload,
        key or settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _auth(user, ver=None):
    token = _encode(
        {
            "user_id": user.id,
            "ver": user.token_version if ver is None else ver,
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
    )
    return {"Authorization": f"Bearer {token}"}


def test_access_token_contains_user_id_and_version(users):
    user = users["teacher_admin01"]

    payload = decode_access_token(create_access_token(user.id, user.token_version))

    assert payload["user_id"] == user.id
    assert payload["ver"] == user.token_version
    assert "roles" not in payload
    assert "capabilities" not in payload


def test_login_issues_token_with_current_version(db, users):
    result = verify_login(db, LoginRequest(username="teacher01", password="123456"))

    payload = decode_access_token(result.token)

    assert payload["user_id"] == users["teacher01"].id
    assert payload["ver"] == users["teacher01"].token_version


def test_token_version_zero_is_valid(client, users):
    response = client.get("/_test/me", headers=_auth(users["zero_version"]))

    assert response.status_code == 200


def test_missing_version_token_returns_401(client, users):
    user = users["student01"]
    token = _encode(
        {
            "user_id": user.id,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
    )

    response = client.get("/_test/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_expired_token_returns_401(client, users):
    user = users["student01"]
    token = _encode(
        {
            "user_id": user.id,
            "ver": user.token_version,
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        }
    )

    response = client.get("/_test/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_wrong_signature_token_returns_401(client, users):
    user = users["student01"]
    token = _encode(
        {
            "user_id": user.id,
            "ver": user.token_version,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        key="wrong-secret",
    )

    response = client.get("/_test/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_version_mismatch_returns_401(client, users):
    user = users["student01"]

    response = client.get(
        "/_test/me",
        headers=_auth(user, ver=user.token_version + 1),
    )

    assert response.status_code == 401


def test_version_increment_invalidates_old_token(client, db, users):
    user = users["student01"]
    headers = _auth(user)

    user.token_version += 1
    db.commit()

    response = client.get("/_test/me", headers=headers)

    assert response.status_code == 401


def test_disabled_user_returns_401(client, users):
    response = client.get("/_test/me", headers=_auth(users["disabled01"]))

    assert response.status_code == 401


@pytest.mark.parametrize("username", list(ROLE_USERS))
def test_role_profile_is_built_from_user_roles(client, users, username):
    response = client.get("/_test/profile", headers=_auth(users[username]))

    assert response.status_code == 200
    body = response.json()
    assert set(body["roles"]) == set(ROLE_USERS[username])
    assert set(body["capabilities"]) == EXPECTED_CAPABILITIES[username]


@pytest.mark.parametrize("username", list(EXPECTED_CAPABILITIES))
@pytest.mark.parametrize("capability", list(Capability))
def test_capability_matrix(client, users, username, capability):
    response = client.get(
        f"/_test/capability/{capability.value}",
        headers=_auth(users[username]),
    )

    expected = 200 if capability.value in EXPECTED_CAPABILITIES[username] else 403
    assert response.status_code == expected


@pytest.mark.parametrize(
    ("username", "expected"),
    [
        ("student01", 403),
        ("teacher01", 403),
        ("admin01", 200),
        ("teacher_admin01", 200),
    ],
)
def test_management_requires_manage_users(client, users, username, expected):
    response = client.get("/_test/management", headers=_auth(users[username]))

    assert response.status_code == expected


@pytest.mark.parametrize(("username", "equipment_id", "expected"), BOOKING_CASES)
def test_booking_capability_depends_on_resource_type(
    client, users, username, equipment_id, expected
):
    payload = {
        "lab_id": 1,
        "date": "2099-01-01",
        "start_time": "09:00",
        "end_time": "10:00",
    }
    if equipment_id is not None:
        payload["equipment_id"] = equipment_id

    response = client.post(
        "/_test/booking",
        json=payload,
        headers=_auth(users[username]),
    )

    assert response.status_code == expected
