from sqlalchemy.orm import Session
from sqlalchemy import func, select
from datetime import datetime

from app.models.user import User
from app.models.lab import Lab
from app.models.equipment import Equipment
from app.models.reservation import Reservation
from app.schemas.reservation import ReservationCreateRequest, ReservationResponse
from app.core.exceptions import BusinessException
from app.core.response import PageResponse


def get_reservation_page_list(
    db: Session,
    current_user: User,
    page: int,
    page_size: int,
    status: int | None = None,
):
    """查询预约记录"""
    stmt = select(Reservation)
    if current_user.role != "admin":
        stmt = stmt.where(Reservation.user_id == current_user.id)
    else:
        stmt = stmt.where(Reservation.status != 3)
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


def audit_reservation(db: Session, reservation_id: int, status: int):
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


def creaet_reservation(
    db: Session, current_user: User, payload: ReservationCreateRequest
):
    """创建预约记录"""
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    if payload.date < current_date:
        raise BusinessException(message="预约日期不能小于当前的日期")
    if payload.end_time < payload.start_time:
        raise BusinessException(message="预约的结束时间不能小于开始时间")
    if payload.date == current_date and payload.start_time < current_time:
        raise BusinessException(message="预约开始时间不能小于当前的时间")

    lab = db.execute(select(Lab).where(Lab.id == payload.lab_id)).scalar_one_or_none()
    if not lab:
        raise BusinessException(message="实验室不存在")
    if lab.status != 1:
        raise BusinessException(message="实验室已关闭")
    if lab.open_time and payload.start_time < lab.open_time:
        raise BusinessException(message="预约时间不能早于实验室的开放时间")
    if lab.close_time and payload.end_time > lab.close_time:
        raise BusinessException(message="预约时间不能晚于实验室的关闭时间")

    # equipment_id 不为空 则表示这次是预约的实验室设备
    if payload.equipment_id:
        equipment = db.execute(
            select(Equipment).where(Equipment.id == payload.equipment_id)
        ).scalar_one_or_none()
        if not equipment:
            raise BusinessException(message="实验室设备不存在")
        if equipment.status != 1:
            raise BusinessException(message="实验室设备正在维修")

    # 实验室或者设备是否是可预约的状态
    stmt = select(Reservation).where(
        Reservation.lab_id == payload.lab_id,
        Reservation.date == payload.date,
        Reservation.status.in_([0, 1]),  # 0表示待审核  1已通过
        Reservation.start_time < payload.end_time,
        Reservation.end_time > payload.start_time,
    )
    if payload.equipment_id:
        stmt = stmt.where(
            Reservation.equipment_id == payload.equipment_id
        )  # 预约实验室设备
    else:
        stmt = stmt.where(Reservation.equipment_id.is_(None))  # 只预约实验室
    res = db.execute(stmt).scalar_one_or_none()
    if res:
        raise BusinessException(message="该时段已预约")

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
