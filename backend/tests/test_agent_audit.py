import json

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.password import hash_password
from app.models.base import Base
from app.models.process_audit import AgentToolCallingAudit
from app.models.user import User, UserRoles
from app.services import agent_tools
from app.services.audit_service import write_failed_tool_calling_audit

PASSWORD_HASH = hash_password("123456")


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False)
    yield TestSessionLocal
    engine.dispose()


@pytest.fixture()
def db(session_factory):
    with session_factory() as session:
        yield session


def _create_user(db, username, roles):
    user = User(
        username=username,
        password=PASSWORD_HASH,
        name=username,
        role="teacher" if "teacher" in roles else "student",
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
    }


def _tool_audits(db):
    db.expire_all()
    return db.scalars(select(AgentToolCallingAudit).order_by(AgentToolCallingAudit.id)).all()


def _json_payload(result):
    assert isinstance(result, str), f"工具应返回 JSON 字符串，实际是 {result!r}"
    return json.loads(result)


def test_get_today_writes_success_tool_audit(db, session_factory, users):
    user = users["student"]
    tools = agent_tools.build_tools(
        db,
        user,
        request_id="req-agent-success",
        audit_session_factory=session_factory,
    )
    tool = next(item for item in tools if item.name == "get_today")

    result = tool.invoke({})

    assert isinstance(result, str)
    audits = _tool_audits(db)
    assert len(audits) == 1

    audit = audits[0]
    assert audit.user_id == user.id
    assert json.loads(audit.roles) == ["student"]
    assert audit.capability == "use_ai"
    assert audit.tool_name == "get_today"
    assert audit.result == "success"
    assert audit.error_code is None
    assert audit.request_id == "req-agent-success"


def test_permission_failure_writes_failed_tool_audit(db, session_factory, users):
    user = users["teacher"]
    tools = agent_tools.build_tools(
        db,
        user,
        request_id="req-agent-denied",
        audit_session_factory=session_factory,
    )
    lab_tool = next(
        item for item in tools if item.name == "create_lab_reservation"
    )

    db.execute(delete(UserRoles).where(UserRoles.user_id == user.id))
    db.add(UserRoles(user_id=user.id, role_code="student"))
    db.commit()

    result = lab_tool.invoke(
        {
            "lab_id": 1,
            "date": "2099-01-01",
            "start_time": "10:00",
            "end_time": "11:00",
        }
    )

    payload = _json_payload(result)
    assert payload["code"] == 403

    audits = _tool_audits(db)
    denied_audits = [
        audit
        for audit in audits
        if audit.tool_name == "create_lab_reservation"
        and audit.result == "failed"
    ]
    assert len(denied_audits) == 1

    audit = denied_audits[0]
    assert audit.user_id == user.id
    assert json.loads(audit.roles) == ["student"]
    assert audit.capability == "book_lab"
    assert audit.error_code == "403"
    assert audit.request_id == "req-agent-denied"


def test_business_failure_writes_failed_tool_audit(db, session_factory, users):
    user = users["teacher"]
    tools = agent_tools.build_tools(
        db,
        user,
        request_id="req-agent-404",
        audit_session_factory=session_factory,
    )
    lab_tool = next(
        item for item in tools if item.name == "create_lab_reservation"
    )

    result = lab_tool.invoke(
        {
            "lab_id": 999999,
            "date": "2099-01-01",
            "start_time": "10:00",
            "end_time": "11:00",
        }
    )

    payload = _json_payload(result)
    assert payload["code"] == 404

    audits = _tool_audits(db)
    failed_audits = [
        audit
        for audit in audits
        if audit.tool_name == "create_lab_reservation"
        and audit.result == "failed"
    ]
    assert len(failed_audits) == 1

    audit = failed_audits[0]
    assert audit.user_id == user.id
    assert json.loads(audit.roles) == ["teacher"]
    assert audit.capability == "book_lab"
    assert audit.error_code == "404"
    assert audit.request_id == "req-agent-404"


def test_write_failed_tool_calling_audit_persists(session_factory):
    write_failed_tool_calling_audit(
        session_factory=session_factory,
        user_id=7,
        roles=json.dumps(["teacher", "admin"]),
        capability="book_lab",
        tool_name="create_lab_reservation",
        request_id="req-audit-core",
        result="failed",
        error_code="403",
    )

    with session_factory() as db:
        audits = db.scalars(
            select(AgentToolCallingAudit).order_by(AgentToolCallingAudit.id)
        ).all()

    assert len(audits) == 1
    audit = audits[0]
    assert audit.user_id == 7
    assert json.loads(audit.roles) == ["teacher", "admin"]
    assert audit.capability == "book_lab"
    assert audit.tool_name == "create_lab_reservation"
    assert audit.result == "failed"
    assert audit.error_code == "403"
    assert audit.request_id == "req-audit-core"