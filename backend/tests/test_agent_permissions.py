import json

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.password import hash_password
from app.models.base import Base
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.reservation import Reservation
from app.models.user import User, UserRoles
from app.services import agent_tools

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
        "admin" if "admin" in roles else ("teacher" if "teacher" in roles else "student")
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
        "student": _create_user(db, "agent_student", ["student"]),
        "teacher": _create_user(db, "agent_teacher", ["teacher"]),
        "admin": _create_user(db, "agent_admin", ["admin"]),
        "teacher_admin": _create_user(db, "agent_teacher_admin", ["teacher", "admin"]),
    }


@pytest.fixture()
def lab_equipment(db):
    lab = Lab(
        name="Agent测试实验室",
        location="A101",
        capacity=20,
        open_time="08:00",
        close_time="18:00",
        status=1,
    )
    db.add(lab)
    db.flush()
    equipment = Equipment(
        lab_id=lab.id,
        name="Agent测试设备",
        spec="T-1",
        quantity=1,
        status=1,
    )
    db.add(equipment)
    db.commit()
    db.refresh(lab)
    db.refresh(equipment)
    return lab, equipment


def _names(tools):
    return {tool.name for tool in tools}


def _payload(result):
    assert isinstance(result, str), f"tool 返回值应为 JSON 字符串，实际是 {result!r}"
    return json.loads(result)


def test_student_tool_list_has_no_lab_booking(db, users):
    names = _names(agent_tools.build_tools(db, users["student"]))

    assert "create_equipment_reservation" in names
    assert "create_lab_reservation" not in names
    assert "search_lab_docs" in names
    assert "list_open_labs" in names
    assert "list_lab_equipments" in names


def test_teacher_tool_list_has_both_booking_tools(db, users):
    names = _names(agent_tools.build_tools(db, users["teacher"]))

    assert "create_lab_reservation" in names
    assert "create_equipment_reservation" in names


def test_admin_tool_list_has_no_booking_tools(db, users):
    names = _names(agent_tools.build_tools(db, users["admin"]))

    assert "create_lab_reservation" not in names
    assert "create_equipment_reservation" not in names
    assert "search_lab_docs" in names


def test_teacher_admin_tool_list_has_both_booking_tools(db, users):
    names = _names(agent_tools.build_tools(db, users["teacher_admin"]))

    assert "create_lab_reservation" in names
    assert "create_equipment_reservation" in names


def test_no_role_gets_audit_tool(db, users):
    for user in users.values():
        names = _names(agent_tools.build_tools(db, user))
        assert "audit_reservation" not in names


def test_admin_direct_tool_access_is_rejected(db, users):
    spec = agent_tools.TOOL_SPEC_BY_NAME["create_lab_reservation"]
    profile, denied = agent_tools._check_tool_access(db, users["admin"].id, spec)

    assert profile is not None
    assert denied is not None
    assert _payload(denied)["code"] == 403


def test_student_direct_lab_tool_access_is_rejected(db, users):
    spec = agent_tools.TOOL_SPEC_BY_NAME["create_lab_reservation"]
    profile, denied = agent_tools._check_tool_access(db, users["student"].id, spec)

    assert profile is not None
    assert denied is not None
    assert _payload(denied)["code"] == 403


def test_teacher_direct_lab_tool_access_is_allowed(db, users):
    spec = agent_tools.TOOL_SPEC_BY_NAME["create_lab_reservation"]
    profile, denied = agent_tools._check_tool_access(db, users["teacher"].id, spec)

    assert profile is not None
    assert denied is None


def test_disabled_user_cannot_call_write_tool(db, users, lab_equipment):
    user = users["teacher"]
    lab, _ = lab_equipment
    tools = agent_tools.build_tools(db, user)
    lab_tool = next(tool for tool in tools if tool.name == "create_lab_reservation")

    user.status = 0
    db.commit()

    result = lab_tool.invoke(
        {
            "lab_id": lab.id,
            "date": "2099-01-01",
            "start_time": "10:00",
            "end_time": "11:00",
        }
    )

    assert _payload(result)["code"] == 403


def test_stale_lab_tool_rechecks_role_after_role_change(db, users, lab_equipment):
    user = users["teacher"]
    lab, _ = lab_equipment
    tools = agent_tools.build_tools(db, user)
    lab_tool = next(tool for tool in tools if tool.name == "create_lab_reservation")

    # 模拟会话中途收回教师角色
    db.execute(delete(UserRoles).where(UserRoles.user_id == user.id))
    db.add(UserRoles(user_id=user.id, role_code="student"))
    db.commit()

    before = db.scalar(select(func.count()).select_from(Reservation))
    result = lab_tool.invoke(
        {
            "lab_id": lab.id,
            "date": "2099-01-01",
            "start_time": "10:00",
            "end_time": "11:00",
        }
    )
    after = db.scalar(select(func.count()).select_from(Reservation))

    assert _payload(result)["code"] == 403
    assert after == before


def test_create_equipment_reservation_returns_structured_success(
    db, users, lab_equipment
):
    user = users["student"]
    lab, equipment = lab_equipment
    tools = agent_tools.build_tools(db, user)
    tool = next(
        item for item in tools if item.name == "create_equipment_reservation"
    )

    result = tool.invoke(
        {
            "lab_id": lab.id,
            "equipment_id": equipment.id,
            "date": "2099-01-01",
            "start_time": "10:00",
            "end_time": "11:00",
        }
    )

    payload = _payload(result)
    assert payload["ok"] is True


def test_create_lab_reservation_returns_structured_business_error(
    db, users, lab_equipment
):
    user = users["teacher"]
    tools = agent_tools.build_tools(db, user)
    tool = next(item for item in tools if item.name == "create_lab_reservation")

    result = tool.invoke(
        {
            "lab_id": 999999,
            "date": "2099-01-01",
            "start_time": "10:00",
            "end_time": "11:00",
        }
    )

    payload = _payload(result)
    assert payload["ok"] is False
    assert payload["code"] == 404