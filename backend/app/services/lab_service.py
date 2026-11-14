from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select

from app.core.response import PageResponse
from app.models.lab import Lab
from app.schemas.lab import (
    LabClosedDayRequest,
    LabClosedDayResponse,
    LabDetailResponse,
    LabResponse,
    LabCreateRequest,
    LabUpdateRequest,
)
from app.core.exceptions import BusinessException
from app.models.equipment import Equipment
from app.models.reservation import Reservation
from app.models.lab_closed_day import LabClosedDay


def get_labs_page_list(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    keywords: str | None = None,
    status: int | None = None,
) -> PageResponse:
    """分页模糊查询实验室列表"""
    if page < 1:
        raise BusinessException(code=422, message="页码必须大于等于1")
    if page_size < 1 or page_size > 100:
        raise BusinessException(code=422, message="每页数量必须在1-100之间")

    stmt = select(Lab)
    if keywords is not None and keywords.strip() != "":
        stmt = stmt.where(
            or_(Lab.name.ilike(f"%{keywords}%"), Lab.location.ilike(f"%{keywords}%"))
        )
    if status is not None:
        stmt = stmt.where(Lab.status == status)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()

    items = db.execute(
        stmt.order_by(Lab.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars()

    return PageResponse(
        list=[LabResponse.model_validate(item) for item in items], total=total
    )


def get_lab(db: Session, lab_id: int) -> LabDetailResponse:
    lab = db.execute(select(Lab).where(Lab.id == lab_id)).scalar_one_or_none()
    if not lab:
        raise BusinessException(code=404, message="实验室不存在")
    closed_days = (
        db.execute(
            select(LabClosedDay)
            .where(LabClosedDay.lab_id == lab_id)
            .order_by(LabClosedDay.date.desc())
        )
        .scalars()
        .all()
    )
    closed_days_response = [
        LabClosedDayResponse.model_validate(closed_day) for closed_day in closed_days
    ]
    return LabDetailResponse(
        **LabResponse.model_validate(lab).model_dump(), closed_days=closed_days_response
    )


def get_lab_closed_days(db: Session, lab_id: int) -> list[LabClosedDayResponse]:
    """获取实验室闭馆日期列表"""
    lab = db.execute(select(Lab).where(Lab.id == lab_id)).scalar_one_or_none()
    if not lab:
        raise BusinessException(code=404, message="实验室不存在")
    closed_days = (
        db.execute(
            select(LabClosedDay)
            .where(LabClosedDay.lab_id == lab_id)
            .order_by(LabClosedDay.date.desc())
        )
        .scalars()
        .all()
    )
    return [
        LabClosedDayResponse.model_validate(closed_day) for closed_day in closed_days
    ]


def create_lab(db: Session, payload: LabCreateRequest) -> LabResponse:
    """实验室管理-新增实验室"""
    if not payload.name or payload.name.strip() == "":
        raise BusinessException(code=422, message="实验室名称不能为空")
    payload.name = payload.name.strip()
    if payload.open_time is None or payload.close_time is None:
        raise BusinessException(code=422, message="实验室开放时间和关闭时间不能为空")
    if payload.open_time >= payload.close_time:
        raise BusinessException(code=422, message="实验室开放时间必须小于关闭时间")

    try:
        existing = db.execute(
            select(Lab).where(Lab.name == payload.name)
        ).scalar_one_or_none()
    except Exception as e:
        raise BusinessException(code=500, message="查询实验室时发生错误")

    if existing:
        raise BusinessException(code=409, message="实验室已存在")

    lab = Lab(**payload.model_dump())
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def update_lab(db: Session, lab_id: int, payload: LabUpdateRequest) -> LabResponse:
    """实验室管理-更新实验室"""
    lab = db.execute(select(Lab).where(Lab.id == lab_id)).scalar_one_or_none()
    if not lab:
        raise BusinessException(code=404, message="实验室不存在")

    payload_data = payload.model_dump(exclude_unset=True)
    for field in ("name", "capacity", "status", "open_time", "close_time"):
        if field in payload_data and payload_data[field] is None:
            raise BusinessException(code=422, message=f"{field} 不能为空")

    payload_data["name"] = payload_data.get("name", lab.name).strip()
    if "name" in payload_data and payload_data["name"] is not None:
        if payload_data["name"].strip() == "":
            raise BusinessException(code=422, message="实验室名称不能为空")
        existing = db.execute(
            select(Lab).where(Lab.name == payload_data["name"], Lab.id != lab_id)
        ).scalar()
        if existing:
            raise BusinessException(code=409, message="实验室已存在,请使用其他名称")
    new_open_time = payload_data.get("open_time", lab.open_time)
    new_close_time = payload_data.get("close_time", lab.close_time)
    if new_open_time is not None and new_close_time is not None:
        if new_open_time >= new_close_time:
            raise BusinessException(code=422, message="实验室开放时间必须小于关闭时间")

    for field, value in payload_data.items():
        setattr(lab, field, value)

    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def update_lab_closed_day(
    db: Session, lab_id: int, payload: LabClosedDayRequest
) -> LabClosedDayResponse:
    """实验室管理-更新实验室闭馆日期"""
    lab = db.execute(select(Lab).where(Lab.id == lab_id)).scalar_one_or_none()
    if not lab:
        raise BusinessException(code=404, message="实验室不存在")

    today = datetime.now().date()
    if payload.date is None or payload.date < today:
        raise BusinessException(code=422, message="闭馆日期必须在今天及以后")
    closed_day = db.execute(
        select(LabClosedDay).where(
            LabClosedDay.lab_id == lab_id, LabClosedDay.date == payload.date
        )
    ).scalar_one_or_none()

    if closed_day:
        closed_day.reason = payload.reason
    else:
        closed_day = LabClosedDay(
            lab_id=lab_id, date=payload.date, reason=payload.reason
        )
        db.add(closed_day)
    db.commit()
    db.refresh(closed_day)

    return LabClosedDayResponse.model_validate(closed_day)


def delete_lab(db: Session, lab_id: int):
    """实验室管理-删除实验室"""
    lab = db.execute(select(Lab).where(Lab.id == lab_id)).scalar_one_or_none()
    if not lab:
        raise BusinessException(code=404, message="实验室不存在")
    has_equipment = db.execute(
        select(Equipment).where(Equipment.lab_id == lab_id)
    ).scalar()
    if has_equipment:
        raise BusinessException(code=409, message="实验室下存在设备，无法删除")
    has_reservation = db.execute(
        select(Reservation).where(Reservation.lab_id == lab_id)
    ).scalar()
    if has_reservation:
        raise BusinessException(code=409, message="实验室下存在预约，无法删除")

    has_closed_days = (
        db.execute(select(LabClosedDay).where(LabClosedDay.lab_id == lab_id))
        .scalars()
        .all()
    )
    for closed_day in has_closed_days:
        db.delete(closed_day)
    db.delete(lab)
    db.commit()


def delete_lab_closed_day(db: Session, lab_id: int, date: datetime.date):
    """实验室管理-删除实验室闭馆日期"""
    lab = db.execute(select(Lab).where(Lab.id == lab_id)).scalar_one_or_none()
    if not lab:
        raise BusinessException(code=404, message="实验室不存在")
    if date < datetime.now().date():
        raise BusinessException(code=422, message="已结束无法删除")
    closed_day = db.execute(
        select(LabClosedDay).where(
            LabClosedDay.lab_id == lab_id, LabClosedDay.date == date
        )
    ).scalar_one_or_none()

    if not closed_day:
        raise BusinessException(code=404, message="闭馆日期不存在")

    db.delete(closed_day)
    db.commit()
