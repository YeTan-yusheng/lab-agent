from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, func, or_, select, update
from datetime import datetime, timedelta
from types import SimpleNamespace
import asyncio
import logging
import time
import uuid

from app.models.user import User
from app.models.lab import Lab
from app.models.equipment import Equipment
from app.models.reservation import Reservation
from app.models.reservation_status_history import ReservationStatusHistory
from app.core.exceptions import BusinessException
from app.core.response import PageResponse
from app.core.database import SessionLocal
from app.schemas.reservation import (
    ReservationCreateRequest,
    ReservationResponse,
    AvailabilityRequest,
    AvailabilityResponse,
    ConflictInfo,
    DayAvailabilityRequest,
    DayAvailabilityResponse,
    TimeRange,
    ReservationHistoryItem,
)
from app.core.permissions import (
    Capability,
    get_role_profile,
    booking_capability,
)
from app.core.reservation_lifecycle import (
    ReservationAction,
    ReservationErrorCode,
    ReservationStatus,
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
from app.services.notification_service import notify_reservation_event

TIME_INTERVAL = 10  # 预约时间间隔，单位分钟

logger = logging.getLogger(__name__)


def _record_status_change(
    db: Session,
    reservation: Reservation,
    *,
    from_status: int | None,
    to_status: int,
    action: ReservationAction,
    actor_id: int | None,
    request_id: str | None,
    reason: str | None = None,
) -> ReservationStatusHistory:
    """改状态并写历史、调用方负责提交事务。"""
    if reservation.id is None:
        db.flush()
    request_id = request_id or uuid.uuid4().hex
    reservation.status = int(to_status)
    history = ReservationStatusHistory(
        reservation_id=reservation.id,
        from_status=from_status,
        to_status=int(to_status),
        action=action.value,
        actor_id=actor_id,
        reason=reason,
        request_id=request_id,
    )
    db.add(history)
    notify_reservation_event(
        db,
        reservation=reservation,
        action=action,
        actor_id=actor_id,
        reason=reason,
        request_id=request_id,
    )
    logger.info(
        "reservation_status_changed",
        extra={
            "request_id": request_id,
            "reservation_id": reservation.id,
            "actor_id": actor_id,
            "action": action.value,
            "from_status": from_status,
            "to_status": int(to_status),
        },
    )
    return history


def _time_to_minutes(value: str | None, default: int) -> int:
    """将时间字符串转换为分钟数"""
    if not value:
        return default
    try:
        hours, minutes = (int(part) for part in value.split(":"))
        return hours * 60 + minutes
    except (TypeError, ValueError):
        return default


def _minutes_to_time(value: int) -> str:
    """将分钟数转换为时间字符串"""
    return f"{value // 60:02d}:{value % 60:02d}"


def _reservation_start_at(reservation: Reservation) -> datetime:
    try:
        return datetime.strptime(
            f"{reservation.date} {reservation.start_time}",
            "%Y-%m-%d %H:%M",
        )
    except ValueError as exc:
        raise BusinessException(
            code=500,
            message="预约时间数据异常",
            error_code=ReservationErrorCode.INTERNAL_ERROR.value,
        ) from exc


def _normalize_date_filter(value: str | None, field: str) -> str | None:
    """将日期字符串规范化为 YYYY-MM-DD 格式"""
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise BusinessException(
            code=422,
            message=f"{field} 格式必须为 YYYY-MM-DD",
            error_code="VALIDATION_ERROR",
        )


def get_reservation_page_list(
    db: Session,
    current_user: User,
    page: int,
    page_size: int,
    status: int | None = None,
    lab_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    mine: bool = False,
):
    """查询预约记录；mine=True 时强制只看本人，否则审核人可看全部。"""
    role_profile = get_role_profile(current_user)
    date_from = _normalize_date_filter(date_from, "date_from")
    date_to = _normalize_date_filter(date_to, "date_to")
    if date_from and date_to and date_from > date_to:
        raise BusinessException(
            code=422,
            message="date_from 不能晚于 date_to",
            error_code="VALIDATION_ERROR",
        )

    stmt = select(Reservation)
    if mine or not role_profile.has(Capability.audit_reservation):
        stmt = stmt.where(Reservation.user_id == current_user.id)
    elif status is None:
        stmt = stmt.where(
            Reservation.status.notin_(
                (ReservationStatus.CANCELLED, ReservationStatus.EXPIRED)
            )
        )

    if status is not None:
        stmt = stmt.where(Reservation.status == status)
    if lab_id is not None:
        stmt = stmt.where(Reservation.lab_id == lab_id)
    if date_from is not None:
        stmt = stmt.where(Reservation.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Reservation.date <= date_to)

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


def get_audit_pending_count(db: Session, current_user: User) -> int:
    role_profile = get_role_profile(current_user)
    if not role_profile.has(Capability.audit_reservation):
        raise BusinessException(
            code=403,
            message="无权限查看待审核数量",
            error_code=ReservationErrorCode.FORBIDDEN.value,
        )
    return db.scalar(
        select(func.count())
        .select_from(Reservation)
        .where(Reservation.status == ReservationStatus.PENDING)
    )


def get_reservation_history(
    db: Session, current_user: User, reservation_id: int
) -> list[ReservationHistoryItem]:
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        raise BusinessException(
            code=404,
            message="预约不存在",
            error_code=ReservationErrorCode.NOT_FOUND.value,
        )

    role_profile = get_role_profile(current_user)
    if reservation.user_id != current_user.id and not role_profile.has(
        Capability.audit_reservation
    ):
        raise BusinessException(
            code=403,
            message="无权限查看预约历史",
            error_code=ReservationErrorCode.FORBIDDEN.value,
        )

    items = db.scalars(
        select(ReservationStatusHistory)
        .where(ReservationStatusHistory.reservation_id == reservation_id)
        .order_by(ReservationStatusHistory.id)
        .options(selectinload(ReservationStatusHistory.actor))
    ).all()
    return [
        ReservationHistoryItem(
            id=item.id,
            action=item.action,
            from_status=item.from_status,
            to_status=item.to_status,
            reason=item.reason,
            actor_name=item.actor.name if item.actor else None,
            request_id=item.request_id,
            create_time=item.create_time,
        )
        for item in items
    ]


def cancel_reservation(
    db: Session,
    reservation_id: int,
    current_user: User,
    reason: str | None = None,
    force: bool = False,
    request_id: str | None = None,
    now: datetime | None = None,
):
    """取消预约：本人 12 小时规则、管理员显式强制取消、取消历史。"""
    role_profile = get_role_profile(current_user)
    is_admin = role_profile.has(Capability.audit_reservation)
    reason = reason.strip() if reason is not None else ""

    if force:
        if not is_admin:
            raise BusinessException(
                code=403,
                message="无权限强制取消预约",
                error_code=ReservationErrorCode.FORBIDDEN.value,
            )
        if not reason:
            raise BusinessException(
                code=422,
                message="强制取消必须填写原因",
                error_code=ReservationErrorCode.CANCEL_REASON_REQUIRED.value,
            )

    try:
        reservation = db.execute(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .with_for_update()
        ).scalar_one_or_none()
        if reservation is None:
            raise BusinessException(
                code=404,
                message="预约不存在",
                error_code=ReservationErrorCode.NOT_FOUND.value,
            )

        is_owner = reservation.user_id == current_user.id
        if not force and not is_owner:
            raise BusinessException(
                code=403,
                message="只能取消本人的预约",
                error_code=ReservationErrorCode.FORBIDDEN.value,
            )

        if reservation.status not in (
            ReservationStatus.PENDING,
            ReservationStatus.APPROVED,
        ):
            raise BusinessException(
                code=409,
                message="当前状态无法取消",
                error_code=ReservationErrorCode.INVALID_STATUS_TRANSITION.value,
            )

        current_time = now or datetime.now()
        start_at = _reservation_start_at(reservation)
        if force and start_at <= current_time:
            raise BusinessException(
                code=409,
                message="预约已开始，无法强制取消",
                error_code=ReservationErrorCode.CANCEL_TOO_LATE.value,
            )
        if (
            not force
            and is_owner
            and reservation.status == ReservationStatus.APPROVED
            and current_time > start_at - timedelta(hours=12)
        ):
            raise BusinessException(
                code=409,
                message="已通过预约需至少提前 12 小时取消",
                error_code=ReservationErrorCode.CANCEL_TOO_LATE.value,
            )

        from_status = reservation.status
        reservation.cancel_reason = reason or None
        reservation.cancelled_by = current_user.id
        _record_status_change(
            db,
            reservation,
            from_status=from_status,
            to_status=ReservationStatus.CANCELLED,
            action=(
                ReservationAction.FORCE_CANCEL if force else ReservationAction.CANCEL
            ),
            actor_id=current_user.id,
            request_id=request_id,
            reason=reason or None,
        )
        db.commit()
    except BusinessException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise BusinessException(
            code=409,
            message="预约状态冲突",
            error_code=ReservationErrorCode.INVALID_STATUS_TRANSITION.value,
        )
    except Exception as exc:
        db.rollback()
        raise BusinessException(
            code=500,
            message="取消预约失败",
            error_code=ReservationErrorCode.INTERNAL_ERROR.value,
        ) from exc


def audit_reservation(
    db: Session,
    current_user: User,
    reservation_id: int,
    status: int,
    reject_reason: str | None = None,
    self_audit: bool = False,
    request_id: str | None = None,
    now: datetime | None = None,
):
    """审核预约记录"""
    role_profile = get_role_profile(current_user)
    if not role_profile.has(Capability.audit_reservation):
        raise BusinessException(
            code=403,
            message="无权限审核预约记录",
            error_code=ReservationErrorCode.FORBIDDEN.value,
        )

    if status not in (ReservationStatus.APPROVED, ReservationStatus.REJECTED):
        raise BusinessException(
            code=422,
            message="审核状态错误",
            error_code=ReservationErrorCode.INVALID_AUDIT_STATUS.value,
        )

    reason = reject_reason.strip() if reject_reason is not None else ""
    if status == ReservationStatus.REJECTED and not reason:
        raise BusinessException(
            code=422,
            message="拒绝预约必须填写原因",
            error_code=ReservationErrorCode.REJECT_REASON_REQUIRED.value,
        )
    if status == ReservationStatus.APPROVED and reason:
        raise BusinessException(
            code=422,
            message="通过预约时不能填写拒绝原因",
            error_code=ReservationErrorCode.REJECT_REASON_NOT_ALLOWED.value,
        )

    try:
        reservation = db.execute(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .with_for_update()
        ).scalar_one_or_none()
        if reservation is None:
            raise BusinessException(
                code=404,
                message="预约不存在",
                error_code=ReservationErrorCode.NOT_FOUND.value,
            )
        if reservation.status != ReservationStatus.PENDING:
            raise BusinessException(
                code=409,
                message="当前状态不支持审核",
                error_code=ReservationErrorCode.INVALID_STATUS_TRANSITION.value,
            )

        is_owner = reservation.user_id == current_user.id
        if is_owner and not self_audit:
            raise BusinessException(
                code=403,
                message="本人预约必须显式自审",
                error_code=ReservationErrorCode.SELF_AUDIT_REQUIRED.value,
            )
        if not is_owner and self_audit:
            raise BusinessException(
                code=422,
                message="只能对本人预约使用自审",
                error_code=ReservationErrorCode.SELF_AUDIT_INVALID.value,
            )

        from_status = reservation.status
        reservation.reviewer_id = current_user.id
        reservation.reviewed_at = now or datetime.now()
        reservation.reject_reason = (
            reason if status == ReservationStatus.REJECTED else None
        )
        reservation.self_audit = is_owner and status == ReservationStatus.APPROVED
        _record_status_change(
            db,
            reservation,
            from_status=from_status,
            to_status=status,
            action=(
                ReservationAction.APPROVE
                if status == ReservationStatus.APPROVED
                else ReservationAction.REJECT
            ),
            actor_id=current_user.id,
            request_id=request_id,
            reason=reason if status == ReservationStatus.REJECTED else None,
        )
        db.commit()
    except BusinessException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise BusinessException(
            code=409,
            message="预约状态冲突",
            error_code=ReservationErrorCode.INVALID_STATUS_TRANSITION.value,
        )
    except Exception as exc:
        db.rollback()
        raise BusinessException(
            code=500,
            message="审核预约失败",
            error_code=ReservationErrorCode.INTERNAL_ERROR.value,
        ) from exc


def create_reservation(
    db: Session,
    current_user: User,
    payload: ReservationCreateRequest,
    request_id: str | None = None,
):
    """创建预约记录"""
    role_profile = get_role_profile(current_user)
    required = booking_capability(payload.equipment_id)
    if not role_profile.has(required):
        raise BusinessException(
            code=403,
            message="无权限预约该类型资源",
            error_code=ReservationErrorCode.FORBIDDEN.value,
        )

    try:
        lab = db.execute(
            select(Lab).where(Lab.id == payload.lab_id).with_for_update()
        ).scalar_one_or_none()
        if lab is None:
            raise BusinessException(
                code=404,
                message="实验室不存在",
                error_code=ReservationErrorCode.NOT_FOUND.value,
            )

        check_result = check_availability(db, payload, lock_conflicts=True)
        if not check_result.available:
            raise BusinessException(
                code=check_result.http_status, message=check_result.message
            )

        reservation = Reservation(
            user_id=current_user.id,
            lab_id=payload.lab_id,
            equipment_id=payload.equipment_id,
            date=payload.date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            remark=payload.remark,
            status=ReservationStatus.PENDING,
        )
        db.add(reservation)
        db.flush()

        _record_status_change(
            db,
            reservation,
            from_status=None,
            to_status=ReservationStatus.PENDING,
            action=ReservationAction.SUBMIT,
            actor_id=current_user.id,
            request_id=request_id,
        )
        db.commit()
    except BusinessException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise BusinessException(
            code=409,
            message="预约冲突",
            error_code=ReservationErrorCode.CONFLICT.value,
        )
    except Exception as exc:
        db.rollback()
        raise BusinessException(
            code=500,
            message="创建预约失败",
            error_code=ReservationErrorCode.INTERNAL_ERROR.value,
        ) from exc


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


def get_day_availability(
    db: Session, current_user: User, payload: DayAvailabilityRequest
) -> DayAvailabilityResponse:
    """返回某天的可预约区间"""
    role_profile = get_role_profile(current_user)
    if not role_profile.has(booking_capability(payload.equipment_id)):
        raise BusinessException(code=403, message="无权限预约该类型资源")

    day = datetime.strptime(payload.date, "%Y-%m-%d").date()

    lab = db.execute(select(Lab).where(Lab.id == payload.lab_id)).scalar_one_or_none()
    if lab is None:
        raise BusinessException(code=404, message="实验室不存在")

    equipment = None
    if payload.equipment_id is not None:
        equipment = db.execute(
            select(Equipment).where(Equipment.id == payload.equipment_id)
        ).scalar_one_or_none()
        if equipment is None:
            raise BusinessException(code=404, message="实验室设备不存在")
        if equipment.lab_id != payload.lab_id:
            raise BusinessException(code=400, message="实验室设备不属于该实验室")

    closed_day = db.scalar(
        select(LabClosedDay.id)
        .where(
            LabClosedDay.lab_id == payload.lab_id,
            LabClosedDay.date == day,
        )
        .limit(1)
    )

    open_minutes = _time_to_minutes(lab.open_time, -1)
    close_minutes = _time_to_minutes(lab.close_time, -1)
    if open_minutes < 0 or close_minutes < 0:
        raise BusinessException(code=500, message="实验室开放时间错误,请联系管理员")

    today = datetime.now().date()
    message = None
    if day < today:
        message = "日期已过去"
    elif lab.status != 1:
        message = "实验室已关闭"
    elif closed_day:
        message = "实验室闭馆"
    elif equipment is not None and equipment.status != 1:
        message = "设备维修中"

    ranges = []
    if message is None:
        conflict_stmt = select(Reservation).where(
            Reservation.lab_id == payload.lab_id,
            Reservation.date == payload.date,
            Reservation.status.in_(OCCUPYING_STATUSES),
        )
        if payload.equipment_id is not None:
            conflict_stmt = conflict_stmt.where(
                or_(
                    Reservation.equipment_id.is_(None),
                    Reservation.equipment_id == payload.equipment_id,
                )
            )

        occupied = []
        for reservation in db.execute(conflict_stmt).scalars().all():
            start = _time_to_minutes(reservation.start_time, -1)
            end = _time_to_minutes(reservation.end_time, -1)
            if start >= 0 and end > start:
                occupied.append((start, end))

        now = datetime.now()
        cursor = open_minutes
        if day == today:
            cursor = max(
                cursor,
                ((now.hour * 60 + now.minute + TIME_INTERVAL - 1) // TIME_INTERVAL)
                * TIME_INTERVAL,
            )

        for start, end in sorted(occupied):
            if end <= cursor:
                continue
            if start > cursor:
                ranges.append((cursor, min(start, close_minutes)))
            cursor = max(cursor, end)
            if cursor >= close_minutes:
                break

        if cursor < close_minutes:
            ranges.append((cursor, close_minutes))

        if not ranges:
            message = "当天无可预约时段"

    return DayAvailabilityResponse(
        date=payload.date,
        open_time=_minutes_to_time(open_minutes),
        close_time=_minutes_to_time(close_minutes),
        current_time=(datetime.now().strftime("%H:%M") if day == today else None),
        message=message,
        ranges=[
            TimeRange(
                start=_minutes_to_time(start),
                end=_minutes_to_time(end),
            )
            for start, end in ranges
        ],
    )


def expire_pending_reservations(
    db: Session | None = None,
    *,
    now: datetime | None = None,
    batch_size: int = 200,
) -> int:
    """把开始时间已过的待审核预约改为过期，并写历史。"""
    owns_session = db is None
    if db is None:
        db = SessionLocal()

    now = now or datetime.now()
    today = now.date().isoformat()
    now_time = now.strftime("%H:%M")
    batch_id = f"system:expire:{uuid.uuid4().hex}"
    total = 0

    try:
        while True:
            started_at = time.perf_counter()
            candidates = db.execute(
                select(
                    Reservation.id,
                    Reservation.user_id,
                    Reservation.lab_id,
                    Reservation.date,
                    Reservation.start_time,
                    Reservation.end_time,
                )
                .where(
                    Reservation.status == ReservationStatus.PENDING,
                    or_(
                        Reservation.date < today,
                        and_(
                            Reservation.date == today,
                            Reservation.start_time <= now_time,
                        ),
                    ),
                )
                .limit(batch_size)
            ).all()
            if not candidates:
                break

            changed = 0
            for candidate in candidates:
                result = db.execute(
                    update(Reservation)
                    .where(
                        Reservation.id == candidate.id,
                        Reservation.status == ReservationStatus.PENDING,
                    )
                    .values(status=ReservationStatus.EXPIRED)
                )
                if result.rowcount == 1:
                    db.add(
                        ReservationStatusHistory(
                            reservation_id=candidate.id,
                            from_status=ReservationStatus.PENDING,
                            to_status=ReservationStatus.EXPIRED,
                            action=ReservationAction.EXPIRE.value,
                            actor_id=None,
                            reason="待审核超时",
                            request_id=batch_id,
                        )
                    )
                    notify_reservation_event(
                        db,
                        reservation=SimpleNamespace(
                            id=candidate.id,
                            user_id=candidate.user_id,
                            lab_id=candidate.lab_id,
                            date=candidate.date,
                            start_time=candidate.start_time,
                            end_time=candidate.end_time,
                        ),
                        action=ReservationAction.EXPIRE,
                        actor_id=None,
                        reason="待审核超时",
                        request_id=batch_id,
                    )
                    changed += 1

            db.commit()
            total += changed
            logger.info(
                "reservation_expired_batch",
                extra={
                    "request_id": batch_id,
                    "candidate_count": len(candidates),
                    "changed_count": changed,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
            if len(candidates) < batch_size or changed == 0:
                break
        if total:
            logger.info(
                "reservation_expired",
                extra={"request_id": batch_id, "changed_count": total},
            )
        return total
    except Exception:
        db.rollback()
        raise
    finally:
        if owns_session:
            db.close()


async def run_expire_scan():
    while True:
        try:
            expire_pending_reservations()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "expire_scan_failed",
                extra={"request_id": "system:expire"},
            )
        await asyncio.sleep(60)
