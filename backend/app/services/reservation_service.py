from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select
from datetime import datetime
import asyncio

from app.models.user import User
from app.models.lab import Lab
from app.models.equipment import Equipment
from app.models.reservation import Reservation
from app.core.exceptions import BusinessException
from app.core.response import PageResponse
from app.core.database import SessionLocal
from app.schemas.reservation import (
    ReservationCreateRequest,
    ReservationResponse,
    AvailabilityRequest,
    AvailabilityResponse,
    ConflictInfo,
)
from app.core.permissions import (
    Capability,
    get_role_profile,
    booking_capability,
)
from app.core.reservation_rules import (
    OCCUPYING_STATUSES,
    RuleResult,
    conflict_scope,
    evaluate_conflicts,
    validate_equipment,
    validate_lab,
    validate_time,
)
from app.models.lab_closed_day import LabClosedDay


def get_reservation_page_list(
    db: Session,
    current_user: User,
    page: int,
    page_size: int,
    status: int | None = None,
):
    """查询预约记录"""
    role_profile = get_role_profile(current_user)

    stmt = select(Reservation)

    if role_profile.has(Capability.audit_reservation):
        stmt = stmt.where(Reservation.status != 3)
    else:
        stmt = stmt.where(Reservation.user_id == current_user.id)
    if status is not None:
        stmt = stmt.where(Reservation.status == status)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()
    items = db.execute(
        stmt.order_by(Reservation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars()

    result = []
    for item in items:
        res = ReservationResponse.model_validate(item)
        res.user_name = item.user.name if item.user else None
        res.lab_name = item.lab.name if item.lab else None
        res.equipment_name = item.equipment.name if item.equipment else None
        res.type = "设备" if item.equipment_id else "实验室"
        result.append(res)
    return PageResponse(list=result, total=total)


def cancel_reservation(db: Session, reservation_id: int, current_user: User):
    reservation = db.execute(
        select(Reservation).where(Reservation.id == reservation_id)
    ).scalar_one_or_none()
    if not reservation:
        raise BusinessException(message="预约不存在")
    if reservation.user_id != current_user.id:
        raise BusinessException(message="无权限", code=403)
    if reservation.status != 0:
        raise BusinessException(message="当前状态无法取消")
    reservation.status = 3
    db.commit()


def audit_reservation(
    db: Session, current_user: User, reservation_id: int, status: int
):
    """审核预约记录"""
    role_profile = get_role_profile(current_user)
    if not role_profile.has(Capability.audit_reservation):
        raise BusinessException(code=403, message="无权限审核预约记录")

    reservation = db.execute(
        select(Reservation).where(Reservation.id == reservation_id)
    ).scalar_one_or_none()
    if status not in [1, 2]:
        raise BusinessException(message="审核状态错误")
    if not reservation:
        raise BusinessException(message="预约不存在")
    if reservation.status != 0:
        raise BusinessException(message="当前状态不支持审核")
    reservation.status = status
    db.commit()


def create_reservation(
    db: Session, current_user: User, payload: ReservationCreateRequest
):
    """创建预约记录"""
    role_profile = get_role_profile(current_user)
    required = booking_capability(payload.equipment_id)
    if not role_profile.has(required):
        raise BusinessException(code=403, message="无权限预约该类型资源")

    try:
        lab = db.execute(
            select(Lab).where(Lab.id == payload.lab_id).with_for_update()
        ).scalar_one_or_none()
        if lab is None:
            raise BusinessException(code=404, message="实验室不存在")

        check_result = check_availability(db, payload, lock_conflicts=True)
        if not check_result.available:
            raise BusinessException(
                code=check_result.http_status, message=check_result.message
            )

        resvervation_model = Reservation(
            user_id=current_user.id,
            lab_id=payload.lab_id,
            equipment_id=payload.equipment_id,
            date=payload.date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            remark=payload.remark,
            status=0,
        )
        db.add(resvervation_model)
        db.commit()
    except BusinessException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise BusinessException(code=409, message="预约冲突")
    except Exception:
        db.rollback()
        raise BusinessException(message="创建预约失败")


def find_conflicts(
    db: Session, payload: AvailabilityRequest, *, lock: bool = False
) -> AvailabilityResponse:
    """查找预约是否冲突"""
    scope = conflict_scope(payload.equipment_id)
    conflict_stmt = select(Reservation).where(
        Reservation.lab_id == payload.lab_id,
        Reservation.date == payload.date,
        Reservation.status.in_(OCCUPYING_STATUSES),
        Reservation.start_time < payload.end_time,
        Reservation.end_time > payload.start_time,
    )

    if not scope.any_reservation:
        conflict_stmt = conflict_stmt.where(
            or_(
                Reservation.equipment_id.is_(None),
                Reservation.equipment_id == scope.equipment_id,
            )
        )
    if lock:
        conflict_stmt = conflict_stmt.with_for_update()
    conflict_reservations = db.execute(conflict_stmt).scalars().all()
    existing_equ_ids = [item.equipment_id for item in conflict_reservations]

    result = evaluate_conflicts(existing_equ_ids, payload.equipment_id)
    if not result.allowed:
        return AvailabilityResponse(
            available=False,
            reason_code=result.reason_code,
            message=result.message,
            conflicts=[
                ConflictInfo(
                    reservation_id=conflict_reservation.id,
                    type=(
                        ("lab")
                        if conflict_reservation.equipment_id is None
                        else "equipment"
                    ),
                    start_time=conflict_reservation.start_time,
                    end_time=conflict_reservation.end_time,
                )
                for conflict_reservation in conflict_reservations
            ],
            http_status=409,
        )
    return AvailabilityResponse(
        available=True, reason_code="OK", message="预约时间可用"
    )


def check_availability(
    db: Session,
    payload: AvailabilityRequest,
    *,
    lock_conflicts: bool = False,
) -> AvailabilityResponse:
    now = datetime.now()
    time_result = validate_time(payload.date, payload.start_time, payload.end_time, now)
    if not time_result.allowed:
        return _to_availability(time_result)

    lab = db.execute(select(Lab).where(Lab.id == payload.lab_id)).scalar_one_or_none()
    closed_days = (
        db.execute(
            select(LabClosedDay.date).where(LabClosedDay.lab_id == payload.lab_id)
        )
        .scalars()
        .all()
    )
    lab_result = validate_lab(
        lab, payload.date, payload.start_time, payload.end_time, closed_days
    )
    if not lab_result.allowed:
        return _to_availability(lab_result)

    if payload.equipment_id is not None:
        equipment = db.execute(
            select(Equipment).where(Equipment.id == payload.equipment_id)
        ).scalar_one_or_none()
        equipment_result = validate_equipment(equipment, payload.lab_id)
        if not equipment_result.allowed:
            return _to_availability(equipment_result)

    conflict_result = find_conflicts(db, payload, lock=lock_conflicts)
    if not conflict_result.available:
        return conflict_result

    return AvailabilityResponse(
        available=True, reason_code="OK", message="预约时间可用"
    )


def _to_availability(result: RuleResult) -> AvailabilityResponse:
    return AvailabilityResponse(
        available=result.allowed,
        reason_code=result.reason_code,
        message=result.message,
        http_status=result.http_status,
    )


# 过期自动释放未审核预约
def expire_pending_reservations():
    db = SessionLocal()
    try:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        now_time = now.strftime("%H:%M")
        items = db.execute(select(Reservation).where(Reservation.status == 0)).scalars()
        changed = False
        for item in items:
            if item.date < today or (item.date == today and item.end_time <= now_time):
                item.status = 3
                changed = True
            if changed:
                db.commit()
    finally:
        db.close()


async def run_expire_scan():
    while True:
        expire_pending_reservations()
        await asyncio.sleep(60)
