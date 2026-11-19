from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.core.reservation_rules import (
    OCCUPYING_STATUSES,
    conflict_scope,
    evaluate_conflicts,
    validate_equipment,
    validate_lab,
    validate_time,
)

NOW = datetime(2026, 11, 19, 10, 30)
LAB = SimpleNamespace(status=1, open_time="08:00", close_time="18:00")
EQUIPMENT = SimpleNamespace(lab_id=1, status=1)


@pytest.mark.parametrize(
    ("date_str", "start", "end"),
    [
        ("2026-11-20", "10:00", "11:00"),
        ("2026-11-19", "10:30", "11:00"),
        ("2026-11-19", "10:31", "11:00"),
        ("2026-12-01", "08:00", "18:00"),
    ],
)
def test_validate_time_accepts_future_slots(date_str, start, end):
    assert validate_time(date_str, start, end, NOW).allowed


@pytest.mark.parametrize("date_str", ["2026/11/20", "2026-02-30", "2099-1-1x"])
def test_validate_time_rejects_bad_date_format(date_str):
    result = validate_time(date_str, "10:00", "11:00", NOW)

    assert result.allowed is False
    assert result.reason_code == "INVALID_DATE_TIME"
    assert result.http_status == 422


@pytest.mark.parametrize(("start", "end"), [("25:00", "26:00"), ("10:00", "11:60")])
def test_validate_time_rejects_bad_time_format(start, end):
    result = validate_time("2026-11-20", start, end, NOW)

    assert result.allowed is False
    assert result.reason_code == "INVALID_DATE_TIME"


@pytest.mark.parametrize(("start", "end"), [("10:00", "10:00"), ("11:00", "10:00")])
def test_validate_time_requires_end_after_start(start, end):
    result = validate_time("2026-11-20", start, end, NOW)

    assert result.allowed is False
    assert result.reason_code == "END_NOT_AFTER_START"


def test_validate_time_rejects_past_date():
    result = validate_time("2026-11-18", "10:00", "11:00", NOW)

    assert result.allowed is False
    assert result.reason_code == "DATE_IN_PAST"


def test_validate_time_rejects_past_start_on_today():
    result = validate_time("2026-11-19", "09:00", "11:00", NOW)

    assert result.allowed is False
    assert result.reason_code == "START_IN_PAST"


def test_validate_lab_rejects_missing_lab():
    result = validate_lab(None, "2026-11-20", "10:00", "11:00", [])

    assert result.allowed is False
    assert result.reason_code == "LAB_NOT_FOUND"
    assert result.http_status == 404


def test_validate_lab_rejects_closed_lab():
    lab = SimpleNamespace(status=0, open_time=None, close_time=None)

    result = validate_lab(lab, "2026-11-20", "10:00", "11:00", [])

    assert result.allowed is False
    assert result.reason_code == "LAB_CLOSED"
    assert result.http_status == 409


@pytest.mark.parametrize(
    "closed_days", [[date(2026, 11, 20)], ["2026-11-20"]]
)
def test_validate_lab_rejects_closed_day(closed_days):
    result = validate_lab(LAB, "2026-11-20", "10:00", "11:00", closed_days)

    assert result.allowed is False
    assert result.reason_code == "LAB_CLOSED_DAY"
    assert result.http_status == 409


def test_validate_lab_accepts_non_closed_day():
    result = validate_lab(
        LAB, "2026-11-20", "10:00", "11:00", [date(2026, 11, 21)]
    )

    assert result.allowed is True


def test_validate_lab_rejects_before_opening_time():
    result = validate_lab(LAB, "2026-11-20", "07:00", "09:00", [])

    assert result.allowed is False
    assert result.reason_code == "BEFORE_OPENING_TIME"
    assert result.http_status == 422


def test_validate_lab_rejects_after_closing_time():
    result = validate_lab(LAB, "2026-11-20", "17:00", "19:00", [])

    assert result.allowed is False
    assert result.reason_code == "AFTER_CLOSING_TIME"
    assert result.http_status == 422


def test_validate_lab_accepts_opening_boundaries():
    result = validate_lab(LAB, "2026-11-20", "08:00", "18:00", [])

    assert result.allowed is True


def test_validate_lab_ignores_missing_opening_hours():
    lab = SimpleNamespace(status=1, open_time=None, close_time=None)

    result = validate_lab(lab, "2026-11-20", "00:00", "23:59", [])

    assert result.allowed is True


def test_validate_equipment_rejects_missing_equipment():
    result = validate_equipment(None, lab_id=1)

    assert result.allowed is False
    assert result.reason_code == "EQUIPMENT_NOT_FOUND"
    assert result.http_status == 404


def test_validate_equipment_rejects_other_lab():
    result = validate_equipment(EQUIPMENT, lab_id=2)

    assert result.allowed is False
    assert result.reason_code == "EQUIPMENT_NOT_IN_LAB"
    assert result.http_status == 400


def test_validate_equipment_rejects_under_repair():
    equipment = SimpleNamespace(lab_id=1, status=0)

    result = validate_equipment(equipment, lab_id=1)

    assert result.allowed is False
    assert result.reason_code == "EQUIPMENT_UNDER_REPAIR"
    assert result.http_status == 409


def test_validate_equipment_accepts_available_equipment():
    assert validate_equipment(EQUIPMENT, lab_id=1).allowed is True


def test_conflict_scope_for_lab_covers_any_reservation():
    scope = conflict_scope(None)

    assert scope.any_reservation is True
    assert scope.equipment_id is None


def test_conflict_scope_for_equipment_covers_lab_and_same_equipment():
    scope = conflict_scope(7)

    assert scope.any_reservation is False
    assert scope.equipment_id == 7


@pytest.mark.parametrize(
    ("requested_equipment_id", "existing_equipment_ids", "allowed", "reason_code"),
    [
        (None, [], True, "OK"),
        (None, [1], False, "LAB_TIME_CONFLICT"),
        (None, [None], False, "LAB_TIME_CONFLICT"),
        (None, [1, 2], False, "LAB_TIME_CONFLICT"),
        (1, [], True, "OK"),
        (1, [2], True, "OK"),
        (1, [2, 3], True, "OK"),
        (1, [None], False, "LAB_TIME_CONFLICT"),
        (1, [1], False, "EQUIPMENT_TIME_CONFLICT"),
        (1, [None, 2], False, "LAB_TIME_CONFLICT"),
        (1, [1, 2], False, "EQUIPMENT_TIME_CONFLICT"),
    ],
)
def test_evaluate_conflicts_matrix(
    requested_equipment_id, existing_equipment_ids, allowed, reason_code
):
    result = evaluate_conflicts(existing_equipment_ids, requested_equipment_id)

    assert result.allowed is allowed
    assert result.reason_code == reason_code
    assert result.http_status == (200 if allowed else 409)


def test_occupying_statuses_are_pending_and_approved():
    assert OCCUPYING_STATUSES == frozenset({0, 1})