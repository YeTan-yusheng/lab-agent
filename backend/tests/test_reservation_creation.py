from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.exceptions import BusinessException
from app.core.password import hash_password
from app.models.base import Base
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.lab_closed_day import LabClosedDay
from app.models.reservation import Reservation
from app.models.user import User, UserRoles
from app.schemas.reservation import ReservationCreateRequest
from app.services import reservation_service

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


@pytest.fixture()
def teacher(db):
    user = User(
        username="creation_teacher",
        password=PASSWORD_HASH,
        name="预约教师",
        role="teacher",
        status=1,
    )
    db.add(user)
    db.flush()
    db.add(UserRoles(user_id=user.id, role_code="teacher"))
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def lab_equipment(db):
    lab = Lab(
        name="接线测试实验室",
        location="C301",
        capacity=10,
        open_time="08:00",
        close_time="18:00",
        status=1,
    )
    db.add(lab)
    db.flush()
    equipment_1 = Equipment(lab_id=lab.id, name="接线设备1", quantity=1, status=1)
    equipment_2 = Equipment(lab_id=lab.id, name="接线设备2", quantity=1, status=1)
    db.add_all([equipment_1, equipment_2])
    db.commit()
    db.refresh(lab)
    db.refresh(equipment_1)
    db.refresh(equipment_2)
    return lab, equipment_1, equipment_2


def _payload(lab, equipment=None, **overrides):
    data = {
        "lab_id": lab.id,
        "date": "2099-01-01",
        "start_time": "10:00",
        "end_time": "11:00",
    }
    if equipment is not None:
        data["equipment_id"] = equipment.id
    data.update(overrides)
    return ReservationCreateRequest(**data)


def _create(db, user, payload):
    reservation_service.create_reservation(db, user, payload)


def _reservation_count(db):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(Reservation))


def test_closed_day_blocks_creation(db, teacher, lab_equipment):
    lab, _, _ = lab_equipment
    db.add(LabClosedDay(lab_id=lab.id, date=date(2099, 1, 1), reason="维护"))
    db.commit()

    with pytest.raises(BusinessException) as exc:
        _create(db, teacher, _payload(lab))

    assert exc.value.code == 409
    assert "闭馆" in exc.value.message
    assert _reservation_count(db) == 0


def test_equipment_from_other_lab_is_rejected(db, teacher, lab_equipment):
    lab, _, _ = lab_equipment
    other_lab = Lab(name="其他实验室", capacity=5, status=1)
    db.add(other_lab)
    db.flush()
    other_equipment = Equipment(
        lab_id=other_lab.id, name="其他设备", quantity=1, status=1
    )
    db.add(other_equipment)
    db.commit()
    db.refresh(other_equipment)

    with pytest.raises(BusinessException) as exc:
        _create(db, teacher, _payload(lab, other_equipment))

    assert exc.value.code == 400


def test_repair_equipment_is_rejected(db, teacher, lab_equipment):
    lab, equipment_1, _ = lab_equipment
    equipment_1.status = 0
    db.commit()

    with pytest.raises(BusinessException) as exc:
        _create(db, teacher, _payload(lab, equipment_1))

    assert exc.value.code == 409


def test_lab_booking_conflicts_with_equipment_booking(db, teacher, lab_equipment):
    lab, equipment_1, _ = lab_equipment
    _create(db, teacher, _payload(lab, equipment_1))

    with pytest.raises(BusinessException) as exc:
        _create(db, teacher, _payload(lab))

    assert exc.value.code == 409


def test_equipment_booking_conflicts_with_lab_booking(db, teacher, lab_equipment):
    lab, equipment_1, _ = lab_equipment
    _create(db, teacher, _payload(lab))

    with pytest.raises(BusinessException) as exc:
        _create(db, teacher, _payload(lab, equipment_1))

    assert exc.value.code == 409


def test_same_equipment_same_slot_conflicts(db, teacher, lab_equipment):
    lab, equipment_1, _ = lab_equipment
    _create(db, teacher, _payload(lab, equipment_1))

    with pytest.raises(BusinessException) as exc:
        _create(db, teacher, _payload(lab, equipment_1))

    assert exc.value.code == 409


def test_different_equipments_can_share_slot(db, teacher, lab_equipment):
    lab, equipment_1, equipment_2 = lab_equipment
    _create(db, teacher, _payload(lab, equipment_1))
    _create(db, teacher, _payload(lab, equipment_2))

    assert _reservation_count(db) == 2


@pytest.mark.parametrize("status", [2, 3])
def test_non_occupying_status_does_not_block(db, teacher, lab_equipment, status):
    lab, _, _ = lab_equipment
    _create(db, teacher, _payload(lab))
    reservation = db.scalars(select(Reservation)).one()
    reservation.status = status
    db.commit()

    _create(db, teacher, _payload(lab))

    assert _reservation_count(db) == 2


def test_adjacent_time_slots_are_allowed(db, teacher, lab_equipment):
    lab, _, _ = lab_equipment
    _create(db, teacher, _payload(lab))
    _create(db, teacher, _payload(lab, start_time="11:00", end_time="12:00"))

    assert _reservation_count(db) == 2