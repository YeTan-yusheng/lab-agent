import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from sqlalchemy import create_engine, delete, event, func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core.exceptions import BusinessException
from app.core.password import hash_password
from app.core.reservation_rules import OCCUPYING_STATUSES
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.lab_closed_day import LabClosedDay
from app.models.reservation import Reservation
from app.models.reservation_status_history import ReservationStatusHistory
from app.models.user import User, UserRoles
from app.schemas.reservation import ReservationCreateRequest
from app.services import reservation_service

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MYSQL_CONCURRENCY") != "1",
    reason="需要 MySQL 测试库，设置 RUN_MYSQL_CONCURRENCY=1",
)

BOOKING_DATE = "2099-01-01"
CLOSED_DATE = date(2099, 1, 1)


@pytest.fixture(scope="module")
def mysql_engine():
    if not settings.test_database_url:
        pytest.skip("TEST_DATABASE_URL 未配置")

    url = make_url(settings.test_database_url)
    if not url.database or not url.database.endswith("_test"):
        pytest.skip("并发测试只允许使用 *_test 数据库")

    engine_options = {}
    if url.get_backend_name() == "mysql":
        # 与生产引擎保持一致：REPEATABLE READ 的间隙锁会让跨实验室插入死锁
        engine_options["isolation_level"] = "READ COMMITTED"
    engine = create_engine(
        settings.test_database_url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        **engine_options,
    )
    if not inspect(engine).has_table("reservations"):
        engine.dispose()
        pytest.skip("测试库尚未迁移")

    @event.listens_for(engine, "connect")
    def set_lock_wait_timeout(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SET SESSION innodb_lock_wait_timeout=10")
        finally:
            cursor.close()

    yield engine
    engine.dispose()


@pytest.fixture()
def concurrency_data(mysql_engine):
    session_factory = sessionmaker(bind=mysql_engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex[:8]

    with session_factory() as db:
        teacher = User(
            username=f"concurrency_teacher_{suffix}",
            password=hash_password("123456"),
            name="并发教师",
            role="teacher",
            status=1,
        )
        student = User(
            username=f"concurrency_student_{suffix}",
            password=hash_password("123456"),
            name="并发学生",
            role="student",
            status=1,
        )
        admin = User(
            username=f"concurrency_admin_{suffix}",
            password=hash_password("123456"),
            name="并发管理员",
            role="admin",
            status=1,
        )
        db.add_all([teacher, student, admin])
        db.flush()
        db.add_all(
            [
                UserRoles(user_id=teacher.id, role_code="teacher"),
                UserRoles(user_id=student.id, role_code="student"),
                UserRoles(user_id=admin.id, role_code="admin"),
            ]
        )

        lab_a = Lab(
            name=f"并发实验室A_{suffix}",
            location="并发测试区A",
            capacity=5,
            open_time="08:00",
            close_time="18:00",
            status=1,
        )
        lab_b = Lab(
            name=f"并发实验室B_{suffix}",
            location="并发测试区B",
            capacity=5,
            open_time="08:00",
            close_time="18:00",
            status=1,
        )
        db.add_all([lab_a, lab_b])
        db.flush()

        equipment_a1 = Equipment(
            lab_id=lab_a.id, name=f"并发设备A1_{suffix}", quantity=1, status=1
        )
        equipment_a2 = Equipment(
            lab_id=lab_a.id, name=f"并发设备A2_{suffix}", quantity=1, status=1
        )
        equipment_b1 = Equipment(
            lab_id=lab_b.id, name=f"并发设备B1_{suffix}", quantity=1, status=1
        )
        db.add_all([equipment_a1, equipment_a2, equipment_b1])
        db.commit()

        data = {
            "session_factory": session_factory,
            "teacher_id": teacher.id,
            "student_id": student.id,
            "admin_id": admin.id,
            "lab_a_id": lab_a.id,
            "lab_b_id": lab_b.id,
            "equipment_a1_id": equipment_a1.id,
            "equipment_a2_id": equipment_a2.id,
            "equipment_b1_id": equipment_b1.id,
        }

    yield data

    with session_factory() as db:
        lab_ids = [data["lab_a_id"], data["lab_b_id"]]
        user_ids = [data["teacher_id"], data["student_id"], data["admin_id"]]
        db.execute(delete(LabClosedDay).where(LabClosedDay.lab_id.in_(lab_ids)))
        reservation_ids = select(Reservation.id).where(Reservation.lab_id.in_(lab_ids))
        db.execute(
            delete(ReservationStatusHistory).where(
                ReservationStatusHistory.reservation_id.in_(reservation_ids)
            )
        )
        db.execute(delete(Reservation).where(Reservation.lab_id.in_(lab_ids)))
        db.execute(delete(Equipment).where(Equipment.lab_id.in_(lab_ids)))
        db.execute(delete(Lab).where(Lab.id.in_(lab_ids)))
        db.execute(delete(UserRoles).where(UserRoles.user_id.in_(user_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _payload(lab_id, equipment_id=None, *, start="10:00", end="11:00"):
    return ReservationCreateRequest(
        lab_id=lab_id,
        equipment_id=equipment_id,
        date=BOOKING_DATE,
        start_time=start,
        end_time=end,
    )


def _attempt(session_factory, user_id, payload, barrier):
    db = session_factory()
    try:
        user = db.get(User, user_id)
        assert user is not None
        _ = list(user.roles)  # 模拟认证阶段先建立事务快照

        barrier.wait(timeout=10)
        try:
            reservation_service.create_reservation(db, user, payload)
            return "success"
        except BusinessException as exc:
            db.rollback()
            return exc.code
    finally:
        db.close()


def _run_concurrently(data, attempts):
    barrier = threading.Barrier(len(attempts))
    with ThreadPoolExecutor(max_workers=len(attempts)) as executor:
        futures = [
            executor.submit(
                _attempt,
                data["session_factory"],
                user_id,
                payload,
                barrier,
            )
            for user_id, payload in attempts
        ]
        return [future.result(timeout=30) for future in futures]


def _reservation_count(data, *, lab_id=None, occupying_only=False):
    with data["session_factory"]() as db:
        stmt = (
            select(func.count())
            .select_from(Reservation)
            .where(Reservation.date == BOOKING_DATE)
        )
        if lab_id is not None:
            stmt = stmt.where(Reservation.lab_id == lab_id)
        if occupying_only:
            stmt = stmt.where(Reservation.status.in_(OCCUPYING_STATUSES))
        return db.scalar(stmt)


def test_concurrent_lab_bookings_allow_only_one_winner(concurrency_data):
    data = concurrency_data
    results = _run_concurrently(
        data,
        [(data["teacher_id"], _payload(data["lab_a_id"]))] * 2,
    )

    assert results.count("success") == 1, results
    assert results.count(409) == 1, results
    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 1


def test_concurrent_same_equipment_bookings_allow_only_one_winner(concurrency_data):
    data = concurrency_data
    results = _run_concurrently(
        data,
        [(data["student_id"], _payload(data["lab_a_id"], data["equipment_a1_id"]))]
        * 2,
    )

    assert results.count("success") == 1, results
    assert results.count(409) == 1, results
    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 1


def test_concurrent_lab_and_equipment_bookings_allow_only_one_winner(
    concurrency_data,
):
    data = concurrency_data
    results = _run_concurrently(
        data,
        [
            (data["teacher_id"], _payload(data["lab_a_id"])),
            (
                data["student_id"],
                _payload(data["lab_a_id"], data["equipment_a1_id"]),
            ),
        ],
    )

    assert results.count("success") == 1, results
    assert results.count(409) == 1, results
    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 1


def test_concurrent_different_equipments_in_same_lab_both_succeed(
    concurrency_data,
):
    data = concurrency_data
    results = _run_concurrently(
        data,
        [
            (
                data["student_id"],
                _payload(data["lab_a_id"], data["equipment_a1_id"]),
            ),
            (
                data["student_id"],
                _payload(data["lab_a_id"], data["equipment_a2_id"]),
            ),
        ],
    )

    assert results == ["success", "success"], results
    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 2


def test_concurrent_different_labs_both_succeed(concurrency_data):
    data = concurrency_data
    results = _run_concurrently(
        data,
        [
            (data["teacher_id"], _payload(data["lab_a_id"])),
            (data["teacher_id"], _payload(data["lab_b_id"])),
        ],
    )

    assert results == ["success", "success"], results
    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 1
    assert _reservation_count(data, lab_id=data["lab_b_id"]) == 1


def test_concurrent_adjacent_slots_both_succeed(concurrency_data):
    data = concurrency_data
    results = _run_concurrently(
        data,
        [
            (
                data["teacher_id"],
                _payload(data["lab_a_id"], start="10:00", end="11:00"),
            ),
            (
                data["teacher_id"],
                _payload(data["lab_a_id"], start="11:00", end="12:00"),
            ),
        ],
    )

    assert results == ["success", "success"], results
    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 2


def test_concurrent_closed_day_requests_are_rejected(concurrency_data):
    data = concurrency_data
    with data["session_factory"]() as db:
        db.add(
            LabClosedDay(
                lab_id=data["lab_a_id"],
                date=CLOSED_DATE,
                reason="并发测试闭馆",
            )
        )
        db.commit()

    results = _run_concurrently(
        data,
        [(data["teacher_id"], _payload(data["lab_a_id"]))] * 2,
    )

    assert results == [409, 409], results
    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 0


@pytest.mark.parametrize(
    ("start", "end"),
    [("07:00", "08:00"), ("17:00", "19:00")],
)
def test_concurrent_out_of_hours_requests_are_rejected(
    concurrency_data, start, end
):
    data = concurrency_data
    results = _run_concurrently(
        data,
        [
            (
                data["teacher_id"],
                _payload(data["lab_a_id"], start=start, end=end),
            )
        ]
        * 2,
    )

    assert results == [422, 422], results
    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 0


def test_concurrent_equipment_from_other_lab_is_rejected(concurrency_data):
    data = concurrency_data
    results = _run_concurrently(
        data,
        [
            (
                data["teacher_id"],
                _payload(data["lab_a_id"], data["equipment_b1_id"]),
            )
        ]
        * 2,
    )

    assert results == [400, 400], results
    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 0


@pytest.mark.parametrize("status", [2, 3])
def test_non_occupying_status_does_not_block_creation(concurrency_data, status):
    data = concurrency_data
    with data["session_factory"]() as db:
        db.add(
            Reservation(
                user_id=data["teacher_id"],
                lab_id=data["lab_a_id"],
                date=BOOKING_DATE,
                start_time="10:00",
                end_time="11:00",
                status=status,
            )
        )
        db.commit()

    results = _run_concurrently(
        data,
        [(data["teacher_id"], _payload(data["lab_a_id"]))],
    )

    assert results == ["success"], results
    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 2
    assert (
        _reservation_count(
            data, lab_id=data["lab_a_id"], occupying_only=True
        )
        == 1
    )


def test_failed_commit_leaves_no_reservation(concurrency_data, monkeypatch):
    data = concurrency_data
    db = data["session_factory"]()
    try:
        user = db.get(User, data["teacher_id"])
        assert user is not None
        _ = list(user.roles)

        def failing_commit():
            db.flush()
            raise RuntimeError("模拟提交失败")

        monkeypatch.setattr(db, "commit", failing_commit)

        with pytest.raises(BusinessException):
            reservation_service.create_reservation(
                db, user, _payload(data["lab_a_id"])
            )
    finally:
        db.close()

    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 0

    # 回滚后锁已释放，可以正常创建
    results = _run_concurrently(
        data,
        [(data["teacher_id"], _payload(data["lab_a_id"]))],
    )
    assert results == ["success"], results
    assert _reservation_count(data, lab_id=data["lab_a_id"]) == 1


def _create_pending_reservation(data, *, user_id=None):
    with data["session_factory"]() as db:
        reservation = Reservation(
            user_id=user_id or data["student_id"],
            lab_id=data["lab_a_id"],
            date=BOOKING_DATE,
            start_time="10:00",
            end_time="11:00",
            status=0,
        )
        db.add(reservation)
        db.commit()
        return reservation.id


def _attempt_audit(session_factory, user_id, reservation_id, status, barrier):
    db = session_factory()
    try:
        user = db.get(User, user_id)
        assert user is not None
        _ = list(user.roles)
        barrier.wait(timeout=10)
        try:
            reservation_service.audit_reservation(
                db, user, reservation_id, status
            )
            return "success"
        except BusinessException as exc:
            db.rollback()
            return exc.code
    finally:
        db.close()


def _attempt_cancel(session_factory, user_id, reservation_id, barrier):
    db = session_factory()
    try:
        user = db.get(User, user_id)
        assert user is not None
        _ = list(user.roles)
        barrier.wait(timeout=10)
        try:
            reservation_service.cancel_reservation(db, reservation_id, user)
            return "success"
        except BusinessException as exc:
            db.rollback()
            return exc.code
    finally:
        db.close()


def _history_count(data, reservation_id):
    with data["session_factory"]() as db:
        return db.scalar(
            select(func.count())
            .select_from(ReservationStatusHistory)
            .where(
                ReservationStatusHistory.reservation_id == reservation_id
            )
        )


def test_concurrent_audits_allow_only_one_winner(concurrency_data):
    data = concurrency_data
    reservation_id = _create_pending_reservation(data)
    barrier = threading.Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _attempt_audit,
                data["session_factory"],
                data["admin_id"],
                reservation_id,
                1,
                barrier,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]

    assert results.count("success") == 1, results
    assert results.count(409) == 1, results
    assert _history_count(data, reservation_id) == 1


def test_audit_and_cancel_race_has_only_one_winner(concurrency_data):
    data = concurrency_data
    reservation_id = _create_pending_reservation(data)
    barrier = threading.Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        audit_future = executor.submit(
            _attempt_audit,
            data["session_factory"],
            data["admin_id"],
            reservation_id,
            1,
            barrier,
        )
        cancel_future = executor.submit(
            _attempt_cancel,
            data["session_factory"],
            data["student_id"],
            reservation_id,
            barrier,
        )
        results = [audit_future.result(timeout=30), cancel_future.result(timeout=30)]

    assert results.count("success") == 1, results
    assert results.count(409) == 1, results

    with data["session_factory"]() as db:
        reservation = db.get(Reservation, reservation_id)
        assert reservation.status in (1, 3)
        history_count = db.scalar(
            select(func.count())
            .select_from(ReservationStatusHistory)
            .where(
                ReservationStatusHistory.reservation_id == reservation_id
            )
        )
        if reservation.status == 1:
            assert history_count == 1
        else:
            assert history_count == 0