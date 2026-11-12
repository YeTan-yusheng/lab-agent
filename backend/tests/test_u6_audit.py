import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import audit_service as audit_module
from app.core.password import hash_password
from app.services.audit_service import add_success_audit, write_failed_audit
from app.models.base import Base
from app.models.process_audit import ActionType, ProcessAudit
from app.models.user import User, UserRoles
from app.schemas.user import RolesUpdateRequest, UserCreateRequest, UserUpdateRequest
from app.services import user_service

PASSWORD_HASH = hash_password("123456")


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False)
    monkeypatch.setattr(audit_module, "SessionLocal", TestSessionLocal)
    with TestSessionLocal() as session:
        yield session
    engine.dispose()


def _create_user(db, username, roles, *, status=1):
    user = User(
        username=username,
        password=PASSWORD_HASH,
        name=username,
        role="admin" if "admin" in roles else "student",
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
        "admin": _create_user(db, "admin_audit", ["admin"]),
        "target": _create_user(db, "target_audit", ["student"]),
    }


@pytest.fixture()
def fake_request():
    return SimpleNamespace(state=SimpleNamespace(request_id="req-test-001"))


def _audits(db):
    db.expire_all()
    return db.scalars(select(ProcessAudit).order_by(ProcessAudit.id)).all()


def test_add_success_audit_persists_when_caller_commits(db):
    add_success_audit(
        db,
        actor_user_id=1,
        target_user_id=2,
        action=ActionType.create_user,
        result="success",
        request_id="req-core-001",
        old_roles=json.dumps([]),
        new_roles=json.dumps(["student"]),
    )
    db.commit()

    audits = _audits(db)
    assert len(audits) == 1
    assert audits[0].actor_user_id == 1
    assert audits[0].target_user_id == 2
    assert audits[0].action == ActionType.create_user
    assert audits[0].old_roles == "[]"
    assert audits[0].new_roles == '["student"]'


def test_write_failed_audit_persists(db):
    write_failed_audit(
        actor_user_id=1,
        target_user_id=2,
        action=ActionType.update_roles,
        result="failed",
        request_id="req-failed-001",
        error_code="SQLAlchemyError",
    )

    audits = _audits(db)
    assert len(audits) == 1
    assert audits[0].result == "failed"
    assert audits[0].error_code == "SQLAlchemyError"
    assert audits[0].request_id == "req-failed-001"


def test_update_user_roles_writes_role_audit(db, users, fake_request):
    admin = users["admin"]
    target = users["target"]

    user_service.update_user_roles(
        fake_request,
        db,
        admin,
        target.id,
        RolesUpdateRequest(roles=["teacher"]),
    )

    audits = _audits(db)
    assert len(audits) == 1
    audit = audits[0]
    assert audit.actor_user_id == admin.id
    assert audit.target_user_id == target.id
    assert audit.action == ActionType.update_roles
    assert audit.result == "success"
    assert audit.request_id == "req-test-001"
    assert json.loads(audit.old_roles) == ["student"]
    assert json.loads(audit.new_roles) == ["teacher"]


def test_create_user_writes_audit_with_target_id(db, users, fake_request):
    admin = users["admin"]

    created = user_service.create_user(
        fake_request,
        db,
        UserCreateRequest(username="created_audit", roles=["student"]),
        admin,
    )

    audits = _audits(db)
    assert len(audits) == 1
    audit = audits[0]
    assert audit.actor_user_id == admin.id
    assert audit.target_user_id == created.id
    assert audit.action == ActionType.create_user
    assert audit.result == "success"
    assert audit.request_id == "req-test-001"
    assert audit.old_roles is None
    assert audit.new_roles is None


def test_disable_user_writes_audit(db, users, fake_request):
    admin = users["admin"]
    target = users["target"]

    user_service.update_user(
        fake_request,
        db,
        target.id,
        UserUpdateRequest(status=0),
        admin,
    )

    audits = _audits(db)
    assert len(audits) == 1
    audit = audits[0]
    assert audit.actor_user_id == admin.id
    assert audit.target_user_id == target.id
    assert audit.action == ActionType.disable_user
    assert audit.result == "success"
    assert audit.request_id == "req-test-001"
    assert audit.old_roles is None
    assert audit.new_roles is None


def test_enable_user_writes_audit(db, users, fake_request):
    admin = users["admin"]
    target = _create_user(db, "disabled_audit", ["student"], status=0)

    user_service.update_user(
        fake_request,
        db,
        target.id,
        UserUpdateRequest(status=1),
        admin,
    )

    audits = _audits(db)
    assert len(audits) == 1
    audit = audits[0]
    assert audit.actor_user_id == admin.id
    assert audit.target_user_id == target.id
    assert audit.action == ActionType.enable_user
    assert audit.result == "success"
    assert audit.request_id == "req-test-001"
    assert audit.old_roles is None
    assert audit.new_roles is None


def test_delete_user_writes_audit(db, users, fake_request):
    admin = users["admin"]
    target = users["target"]

    user_service.delete_user(fake_request, db, target.id, admin)

    audits = _audits(db)
    assert len(audits) == 1
    audit = audits[0]
    assert audit.actor_user_id == admin.id
    assert audit.target_user_id == target.id
    assert audit.action == ActionType.delete_user
    assert audit.result == "success"
    assert audit.request_id == "req-test-001"
    assert audit.old_roles is None
    assert audit.new_roles is None
