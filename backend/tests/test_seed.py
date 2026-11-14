import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.password import verify_password
from app.core.permissions import RoleValidationError, validate_roles
from app.models.base import Base
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.lab_closed_day import LabClosedDay
from app.models.user import User, UserRoles
from scripts.seed import (
    DEMO_CLOSED_DAYS,
    DEMO_EQUIPMENTS,
    DEMO_LABS,
    SEED_USERS,
    seed_demo_data,
    seed_user,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False)
    with SessionLocal() as session:
        yield session
    engine.dispose()


def seed_all(db, reset: bool = False, dry_run: bool = False):
    return [
        seed_user(
            db=db,
            username=username,
            name=name,
            roles=roles,
            password="123456",
            reset=reset,
            dry_run=dry_run,
        )
        for username, name, roles in SEED_USERS
    ]


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def user_roles(db, username: str) -> set[str]:
    user = db.scalar(select(User).where(User.username == username))
    assert user is not None
    return set(
        db.scalars(select(UserRoles.role_code).where(UserRoles.user_id == user.id))
    )


def test_seed_users_are_idempotent(db):
    first = seed_all(db)
    db.commit()

    assert count(db, User) == 4
    assert count(db, UserRoles) == 5
    assert all(result.user_created for result in first)

    second = seed_all(db)
    db.commit()

    assert count(db, User) == 4
    assert count(db, UserRoles) == 5
    assert all(not result.changed for result in second)


def test_seed_users_have_expected_roles_and_passwords(db):
    seed_all(db)
    db.commit()

    users = {user.username: user for user in db.scalars(select(User))}

    for username, name, roles in SEED_USERS:
        user = users[username]
        profile = validate_roles(roles)

        assert user.name == name
        assert user.role == profile.primary_role.value
        assert user.token_version == 0
        assert verify_password("123456", user.password)
        assert user_roles(db, username) == set(roles)


def test_dry_run_does_not_write(db):
    results = seed_all(db, dry_run=True)

    assert count(db, User) == 0
    assert count(db, UserRoles) == 0
    assert all(result.user_created for result in results)


def test_reset_password_and_token_version(db):
    seed_all(db)
    db.commit()

    user = db.scalar(select(User).where(User.username == "student01"))
    assert user is not None
    assert user.token_version == 0

    result = seed_user(
        db=db,
        username="student01",
        name="学生一",
        roles=["student"],
        password="NewPassword123",
        reset=True,
    )
    db.commit()
    db.refresh(user)

    assert result.password_reset is True
    assert verify_password("NewPassword123", user.password)
    assert user.token_version == 1
    assert user_roles(db, "student01") == {"student"}


def test_reset_removes_extra_roles(db):
    seed_all(db)
    db.commit()

    result = seed_user(
        db=db,
        username="teacher_admin01",
        name="教师管理员",
        roles=["teacher"],
        password="123456",
        reset=True,
    )
    db.commit()

    assert result.roles_removed == ["admin"]
    assert user_roles(db, "teacher_admin01") == {"teacher"}


def test_existing_user_without_roles_is_repaired(db):
    seed_user(
        db=db,
        username="student01",
        name="学生一",
        roles=["student"],
        password="123456",
    )
    db.commit()

    user = db.scalar(select(User).where(User.username == "student01"))
    assert user is not None
    db.execute(delete(UserRoles).where(UserRoles.user_id == user.id))
    db.commit()
    assert user_roles(db, "student01") == set()

    result = seed_user(
        db=db,
        username="student01",
        name="学生一",
        roles=["student"],
        password="123456",
    )
    db.commit()

    assert result.roles_added == ["student"]
    assert user_roles(db, "student01") == {"student"}


def test_invalid_role_combination_is_rejected(db):
    with pytest.raises(RoleValidationError):
        seed_user(
            db=db,
            username="bad_user",
            name="非法用户",
            roles=["admin", "student"],
            password="123456",
        )

    assert count(db, User) == 0


def test_demo_data_is_idempotent(db):
    first = seed_demo_data(db)
    db.commit()

    assert first.labs_created == [item["name"] for item in DEMO_LABS]
    assert count(db, Lab) == len(DEMO_LABS)
    assert count(db, Equipment) == sum(
        len(items) for items in DEMO_EQUIPMENTS.values()
    )
    assert count(db, LabClosedDay) == sum(
        len(items) for items in DEMO_CLOSED_DAYS.values()
    )

    second = seed_demo_data(db)
    db.commit()

    assert second.changed is False
    assert count(db, Lab) == len(DEMO_LABS)
    assert count(db, Equipment) == sum(
        len(items) for items in DEMO_EQUIPMENTS.values()
    )
    assert count(db, LabClosedDay) == sum(
        len(items) for items in DEMO_CLOSED_DAYS.values()
    )


def test_demo_closed_days_have_reason(db):
    seed_demo_data(db)
    db.commit()

    closed_days = db.scalars(select(LabClosedDay).order_by(LabClosedDay.lab_id)).all()

    assert len(closed_days) == sum(
        len(items) for items in DEMO_CLOSED_DAYS.values()
    )
    assert all(item.reason for item in closed_days)


def test_demo_closed_day_does_not_overwrite_reason(db):
    seed_demo_data(db)
    db.commit()

    lab = db.scalar(select(Lab).where(Lab.name == "计算机实验室"))
    closed_day = db.scalar(
        select(LabClosedDay).where(
            LabClosedDay.lab_id == lab.id,
            LabClosedDay.date == DEMO_CLOSED_DAYS["计算机实验室"][0]["date"],
        )
    )
    closed_day.reason = "旧原因"
    db.commit()

    result = seed_demo_data(db)
    db.commit()

    assert result.closed_days_created == []
    db.refresh(closed_day)
    assert closed_day.reason == "旧原因"


def test_demo_data_dry_run_does_not_write(db):
    result = seed_demo_data(db, dry_run=True)

    assert len(result.labs_created) == len(DEMO_LABS)
    assert len(result.equipments_created) == sum(
        len(items) for items in DEMO_EQUIPMENTS.values()
    )
    assert len(result.closed_days_created) == sum(
        len(items) for items in DEMO_CLOSED_DAYS.values()
    )
    assert count(db, Lab) == 0
    assert count(db, Equipment) == 0
    assert count(db, LabClosedDay) == 0