import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, delete, event, func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core.exceptions import BusinessException
from app.core.password import hash_password
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.reservation import Reservation
from app.models.user import User, UserRoles
from app.schemas.reservation import ReservationCreateRequest
from app.services import reservation_service

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MYSQL_CONCURRENCY") != "1",
    reason="需要 MySQL 测试库，设置 RUN_MYSQL_CONCURRENCY=1",
)

BOOKING_DATE = "2099-01-01"


@pytest.fixture(scope="module")
def mysql_engine():
    if not settings.test_database_url:
        pytest.skip("TEST_DATABASE_URL 未配置")

    url = make_url(settings.test_database_url)
    if not url.database or not url.database.endswith("_test"):
        pytest.skip("并发测试只允许使用 *_test 数据库")

    engine = create_engine(
        settings.test_database_url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
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
        user = User(
            username=f"concurrency_{suffix}",
            password=hash_password("123456"),
            name="并发教师",
            role="teacher",
            status=1,
        )
        db.add(user)
        db.flush()
        db.add(UserRoles(user_id=user.id, role_code="teacher"))

        lab = Lab(
            name=f"并发实验室_{suffix}",
            location="并发测试区",
            capacity=5,
            open_time="08:00",
            close_time="18:00",
            status=1,
        )
        db.add(lab)
        db.flush()
        equipment = Equipment(
            lab_id=lab.id,
            name=f"并发设备_{suffix}",
            quantity=1,
            status=1,
        )
        db.add(equipment)
        db.commit()

        data = {
            "session_factory": session_factory,
            "user_id": user.id,
            "lab_id": lab.id,
            "equipment_id": equipment.id,
        }

    yield data

    with session_factory() as db:
        db.execute(delete(Reservation).where(Reservation.lab_id == data["lab_id"]))
        db.execute(delete(Equipment).where(Equipment.lab_id == data["lab_id"]))
        db.execute(delete(Lab).where(Lab.id == data["lab_id"]))
        db.execute(delete(UserRoles).where(UserRoles.user_id == data["user_id"]))
        db.execute(delete(User).where(User.id == data["user_id"]))
        db.commit()


def _create_once(session_factory, user_id, lab_id, equipment_id, barrier, results):
    db = session_factory()
    try:
        user = db.get(User, user_id)
        assert user is not None
        _ = list(user.roles)  # 模拟认证阶段先建立事务快照

        payload = ReservationCreateRequest(
            lab_id=lab_id,
            equipment_id=equipment_id,
            date=BOOKING_DATE,
            start_time="10:00",
            end_time="11:00",
        )
        barrier.wait(timeout=5)
        try:
            reservation_service.create_reservation(db, user, payload)
            results.append("success")
        except BusinessException as exc:
            db.rollback()
            results.append(exc.code)
    finally:
        db.close()


def test_concurrent_creation_allows_only_one_winner(concurrency_data):
    barrier = threading.Barrier(2)
    results = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _create_once,
                concurrency_data["session_factory"],
                concurrency_data["user_id"],
                concurrency_data["lab_id"],
                concurrency_data["equipment_id"],
                barrier,
                results,
            )
            for _ in range(2)
        ]
        for future in futures:
            future.result(timeout=30)

    assert results.count("success") == 1, results
    assert results.count(409) == 1, results

    with concurrency_data["session_factory"]() as db:
        count = db.scalar(
            select(func.count())
            .select_from(Reservation)
            .where(
                Reservation.lab_id == concurrency_data["lab_id"],
                Reservation.date == BOOKING_DATE,
            )
        )
    assert count == 1