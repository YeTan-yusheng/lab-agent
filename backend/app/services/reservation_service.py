from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime

from app.models.user import User
from app.models.lab import Lab
from app.models.equipment import Equipment
from app.models.reservation import Reservation
from app.schemas.reservation import ReservationCreateRequest
from app.core.exceptions import BusinessException


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
