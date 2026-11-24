from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.reservation_lifecycle import (
    ReservationAction,
    ReservationErrorCode,
    ReservationStatus,
)
from app.models import Reservation, ReservationStatusHistory
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


def _reservation(**overrides):
    values = {
        "user_id": 1,
        "lab_id": 1,
        "date": "2026-12-01",
        "start_time": "09:00",
        "end_time": "10:00",
    }
    values.update(overrides)
    return Reservation(**values)


def test_reservation_lifecycle_enums():
    assert ReservationStatus.PENDING == 0
    assert ReservationStatus.EXPIRED == 4
    assert ReservationAction.FORCE_CANCEL == "force_cancel"
    assert ReservationErrorCode.CONFLICT == "RESERVATION_CONFLICT"


def test_reservation_status_check_constraint(db):
    db.add(_reservation(status=5))

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize("status", [0, 1, 2, 3, 4])
def test_reservation_accepts_valid_status(db, status):
    reservation = _reservation(status=status)
    db.add(reservation)
    db.commit()

    assert reservation.id is not None
    assert reservation.status == status


def test_new_reservation_fields_defaults(db):
    reservation = _reservation()
    db.add(reservation)
    db.flush()

    assert reservation.status == 0
    assert reservation.self_audit is False
    assert reservation.reviewer_id is None
    assert reservation.reviewed_at is None
    assert reservation.reject_reason is None
    assert reservation.cancel_reason is None
    assert reservation.cancelled_by is None


def test_new_reservation_fields_can_be_set(db):
    reviewed_at = datetime(2026, 11, 24, 10, 30)
    reservation = _reservation(
        status=ReservationStatus.APPROVED,
        reviewer_id=2,
        reviewed_at=reviewed_at,
        reject_reason="不符合要求",
        cancel_reason="临时调整",
        cancelled_by=2,
        self_audit=True,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    assert reservation.reviewer_id == 2
    assert reservation.reviewed_at == reviewed_at
    assert reservation.reject_reason == "不符合要求"
    assert reservation.cancel_reason == "临时调整"
    assert reservation.cancelled_by == 2
    assert reservation.self_audit is True


def test_reservation_status_history_append_and_order(db):
    reservation = _reservation()
    db.add(reservation)
    db.flush()

    db.add_all(
        [
            ReservationStatusHistory(
                reservation_id=reservation.id,
                from_status=None,
                to_status=ReservationStatus.PENDING,
                action=ReservationAction.SUBMIT,
                actor_id=reservation.user_id,
                request_id="req-submit",
            ),
            ReservationStatusHistory(
                reservation_id=reservation.id,
                from_status=ReservationStatus.PENDING,
                to_status=ReservationStatus.APPROVED,
                action=ReservationAction.APPROVE,
                actor_id=2,
                reason=None,
                request_id="req-approve",
            ),
        ]
    )
    db.commit()

    rows = db.scalars(
        select(ReservationStatusHistory)
        .where(ReservationStatusHistory.reservation_id == reservation.id)
        .order_by(ReservationStatusHistory.id)
    ).all()

    assert [row.action for row in rows] == ["submit", "approve"]
    assert rows[0].from_status is None
    assert rows[0].to_status == 0
    assert rows[1].from_status == 0
    assert rows[1].to_status == 1
    assert rows[1].actor_id == 2
    assert rows[1].request_id == "req-approve"


def test_reservation_status_history_requires_request_id(db):
    reservation = _reservation()
    db.add(reservation)
    db.flush()
    db.add(
        ReservationStatusHistory(
            reservation_id=reservation.id,
            from_status=None,
            to_status=ReservationStatus.PENDING,
            action=ReservationAction.SUBMIT,
            actor_id=reservation.user_id,
            request_id=None,
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_lifecycle_indexes_exist(db):
    inspector = inspect(db.bind)

    reservation_indexes = {
        index["name"] for index in inspector.get_indexes("reservations")
    }
    history_indexes = {
        index["name"]
        for index in inspector.get_indexes("reservation_status_history")
    }

    assert "ix_reservations_user_status_id" in reservation_indexes
    assert "ix_reservations_status_date_start" in reservation_indexes
    assert "ix_reservation_status_history_reservation_id" in history_indexes
    assert "ix_reservation_status_history_actor_time" in history_indexes
    assert "ix_reservation_status_history_action_time" in history_indexes