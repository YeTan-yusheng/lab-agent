from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.core.response import PageResponse
from app.models.equipment import Equipment
from app.schemas.equipment import (
    EquipmentCreateRequest,
    EquipmentDetailResponse,
    EquipmentResponse,
    EquipmentUpdateRequest,
)
from app.core.exceptions import BusinessException
from app.models.lab import Lab
from app.models.reservation import Reservation


def get_equipment_page_list(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    keywords: str | None = None,
    lab_id: int | None = None,
    status: int | None = None,
) -> PageResponse:
    """模糊分页查询设备列表"""
    if page < 1:
        raise BusinessException(code=422, message="页码必须大于等于1")
    if page_size < 1 or page_size > 100:
        raise BusinessException(code=422, message="每页数量必须在1-100之间")

    stmt = select(Equipment)
    if lab_id is not None:
        stmt = stmt.where(Equipment.lab_id == lab_id)
    if keywords is not None and keywords.strip() != "":
        stmt = stmt.where(Equipment.name.ilike(f"%{keywords}%"))
    if status is not None:
        stmt = stmt.where(Equipment.status == status)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()
    items = db.execute(
        stmt.order_by(Equipment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars()

    result = []
    for item in items:
        res = EquipmentResponse.model_validate(item)
        res.lab_name = item.lab.name if item.lab else None
        result.append(res)
    return PageResponse(list=result, total=total)


def get_equipment(db: Session, equipment_id: int) -> EquipmentDetailResponse:
    """获取设备详情"""
    equipment = db.execute(
        select(Equipment).where(Equipment.id == equipment_id)
    ).scalar_one_or_none()
    if not equipment:
        raise BusinessException(code=404, message="实验设备不存在")
    res = EquipmentDetailResponse.model_validate(equipment)
    res.lab_name = equipment.lab.name if equipment.lab else None
    res.lab_status = equipment.lab.status if equipment.lab else None
    return res


def create_equipment(db: Session, payload: EquipmentCreateRequest) -> EquipmentResponse:
    """新增实验设备"""
    # 判断实验室是否存在
    lab_existing = db.execute(
        select(Lab).where(Lab.id == payload.lab_id)
    ).scalar_one_or_none()
    if not lab_existing:
        raise BusinessException(code=404, message="实验室不存在")
    # 判断设备是否存在
    if payload.name.strip() == "":
        raise BusinessException(code=422, message="设备名称不能为空")
    payload.name = payload.name.strip()
    try:
        existing = db.execute(
            select(Equipment).where(
                Equipment.name == payload.name, Equipment.lab_id == payload.lab_id
            )
        ).scalar_one_or_none()
    except Exception as e:
        raise BusinessException(code=500, message="查询设备时发生错误")
    if existing:
        raise BusinessException(code=409, message="实验设备已存在")

    equipment = Equipment(**payload.model_dump())
    db.add(equipment)
    db.commit()
    db.refresh(equipment)
    res = EquipmentResponse.model_validate(equipment)
    res.lab_name = equipment.lab.name if equipment.lab else None
    return res


def update_equipment(
    db: Session, equipment_id, payload: EquipmentUpdateRequest
) -> EquipmentResponse:
    """更新"""
    equipment = db.execute(
        select(Equipment).where(Equipment.id == equipment_id)
    ).scalar_one_or_none()
    if not equipment:
        raise BusinessException(code=404, message="实验设备不存在")

    payload_data = payload.model_dump(exclude_unset=True)
    for field in ("lab_id", "name", "quantity", "status"):
        if field in payload_data and payload_data[field] is None:
            raise BusinessException(code=422, message=f"{field} 不能为空")

    name = payload_data.get("name", equipment.name).strip()
    if name == "":
        raise BusinessException(code=422, message="设备名称不能为空")
    lab_id = payload_data.get("lab_id", equipment.lab_id)
    lab = db.execute(select(Lab).where(Lab.id == lab_id)).scalar_one_or_none()
    if not lab:
        raise BusinessException(code=404, message="实验室不存在")

    existing = db.execute(
        select(Equipment).where(
            Equipment.lab_id == lab_id,
            Equipment.name == name,
            Equipment.id != equipment.id,
        )
    ).scalar_one_or_none()
    if existing:
        raise BusinessException(code=409, message="同一个实验室不能存在同名设备")

    payload_data["name"] = name
    for filed, value in payload_data.items():
        setattr(equipment, filed, value)

    db.commit()
    db.refresh(equipment)
    res = EquipmentResponse.model_validate(equipment)
    res.lab_name = equipment.lab.name if equipment.lab else None
    return res


def delete_equipment(db: Session, equipment_id: int):
    """删除实验设备"""
    equipment = db.execute(
        select(Equipment).where(Equipment.id == equipment_id)
    ).scalar_one_or_none()
    if not equipment:
        raise BusinessException(code=404, message="实验设备不存在")
    has_reservation = db.execute(
        select(Reservation).where(Reservation.equipment_id == equipment_id)
    ).scalar()
    if has_reservation:
        raise BusinessException(code=409, message="设备下存在预约，无法删除")
    db.delete(equipment)
    db.commit()
