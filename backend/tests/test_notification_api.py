from datetime import datetime

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
from app.models import Notification, User, UserRoles
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


def _create_user(db, username):
    user = User(
        username=username,
        password=hash_password("123456"),
        name=username,
        role="student",
        status=1,
    )
    db.add(user)
    db.flush()
    db.add(UserRoles(user_id=user.id, role_code="student"))
    db.commit()
    db.refresh(user)
    return user


def _notification(user, dedupe_key, *, is_read=False, read_at=None):
    return Notification(
        user_id=user.id,
        type="reservation_approved",
        title="预约已通过",
        content="你预约的实验室已通过。",
        reservation_id=None,
        is_read=is_read,
        read_at=read_at,
        dedupe_key=dedupe_key,
    )


def _login(client, username):
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "123456"},
    )
    assert response.json()["code"] == 200
    return {"Authorization": f"Bearer {response.json()['data']['token']}"}


def test_notification_list_requires_login(client):
    response = client.get("/api/notification/list")

    assert response.status_code == 401


def test_list_only_returns_current_user_notifications(client, db):
    user = _create_user(db, "notify_api_user")
    other = _create_user(db, "notify_api_other")
    db.add_all(
        [
            _notification(user, "api:inapp:1"),
            _notification(other, "api:inapp:2"),
        ]
    )
    db.commit()

    response = client.get(
        "/api/notification/list",
        headers=_login(client, "notify_api_user"),
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["code"] == 200
    assert payload["data"]["total"] == 1
    item = payload["data"]["list"][0]
    assert item["title"] == "预约已通过"
    assert item["is_read"] is False
    assert "dedupe_key" not in item


def test_list_filters_and_paginates(client, db):
    user = _create_user(db, "notify_filter_user")
    db.add_all(
        [
            _notification(user, "api:filter:1", is_read=False),
            _notification(user, "api:filter:2", is_read=False),
            _notification(
                user,
                "api:filter:3",
                is_read=True,
                read_at=datetime(2026, 11, 26, 10, 0),
            ),
        ]
    )
    db.commit()
    headers = _login(client, "notify_filter_user")

    unread = client.get(
        "/api/notification/list?is_read=false&page=1&page_size=1",
        headers=headers,
    ).json()["data"]
    assert unread["total"] == 2
    assert len(unread["list"]) == 1

    read = client.get("/api/notification/list?is_read=true", headers=headers).json()[
        "data"
    ]
    assert read["total"] == 1
    assert read["list"][0]["is_read"] is True


def test_unread_count(client, db):
    user = _create_user(db, "notify_count_user")
    db.add_all(
        [
            _notification(user, "api:count:1", is_read=False),
            _notification(user, "api:count:2", is_read=False),
            _notification(
                user,
                "api:count:3",
                is_read=True,
                read_at=datetime(2026, 11, 26, 10, 0),
            ),
        ]
    )
    db.commit()

    response = client.get(
        "/api/notification/unread-count",
        headers=_login(client, "notify_count_user"),
    )

    assert response.json()["data"]["count"] == 2


def test_mark_read_is_idempotent(client, db):
    user = _create_user(db, "notify_read_user")
    item = _notification(user, "api:read:1")
    db.add(item)
    db.commit()
    headers = _login(client, "notify_read_user")

    first = client.put(f"/api/notification/{item.id}/read", headers=headers)
    assert first.status_code == 200
    db.expire_all()
    loaded = db.get(Notification, item.id)
    assert loaded.is_read is True
    assert loaded.read_at is not None
    first_read_at = loaded.read_at

    second = client.put(f"/api/notification/{item.id}/read", headers=headers)
    assert second.status_code == 200
    db.expire_all()
    loaded = db.get(Notification, item.id)
    assert loaded.read_at == first_read_at


def test_cannot_read_other_user_notification(client, db):
    _create_user(db, "notify_owner_user")
    other = _create_user(db, "notify_other_user")
    item = _notification(other, "api:other:1")
    db.add(item)
    db.commit()

    response = client.put(
        f"/api/notification/{item.id}/read",
        headers=_login(client, "notify_owner_user"),
    )

    assert response.status_code == 404
    assert response.json()["error_code"] == "NOTIFICATION_NOT_FOUND"
    db.expire_all()
    assert db.get(Notification, item.id).is_read is False


def test_read_all_only_updates_current_user(client, db):
    user = _create_user(db, "notify_all_user")
    other = _create_user(db, "notify_all_other")
    user_items = [
        _notification(user, "api:all:1"),
        _notification(user, "api:all:2"),
    ]
    other_item = _notification(other, "api:all:3")
    db.add_all([*user_items, other_item])
    db.commit()
    headers = _login(client, "notify_all_user")

    response = client.put("/api/notification/read-all", headers=headers)
    assert response.json()["data"]["updated"] == 2
    db.expire_all()
    assert all(db.get(Notification, item.id).is_read is True for item in user_items)
    assert db.get(Notification, other_item.id).is_read is False

    count = client.get("/api/notification/unread-count", headers=headers).json()
    assert count["data"]["count"] == 0


def test_page_size_is_bounded(client, db):
    _create_user(db, "notify_validate_user")
    headers = _login(client, "notify_validate_user")

    response = client.get(
        "/api/notification/list?page_size=51",
        headers=headers,
    )

    assert response.status_code == 422