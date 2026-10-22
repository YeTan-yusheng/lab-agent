from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func

from app.core.response import PageResponse
from app.models.equipment import Equipment
from app.schemas.equipment import (
    EquipmentCreateRequest,
    EquipmentResponse,
    EquipmentUpdateRequest,
)
from app.core.exceptions import BusinessException
from app.models.lab import Lab


def get_equipment_page_list(
    db: Session,
    page: int,
    page_size: int,
    keywords: str | None = None,
    lab_id: int | None = None,
) -> PageResponse:
    """模糊分页查询设备列表"""
    stmt = select(Equipment)
    if lab_id:
        stmt = stmt.where(Equipment.lab_id == lab_id)
    if keywords:
        stmt = stmt.where(Equipment.name.ilike(f"%{keywords}%"))

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


def create_equipment(db: Session, payload: EquipmentCreateRequest) -> EquipmentResponse:
    """新增实验设备"""
    # 判断实验室是否存在
    lab_existing = db.execute(
        select(Lab).where(Lab.id == payload.lab_id)
    ).scalar_one_or_none()
    if not lab_existing:
        raise BusinessException(message="实验室不存在")
    # 判断设备是否存在
    existing = db.execute(
        select(Equipment).where(
            Equipment.name == payload.name, Equipment.lab_id == payload.lab_id
        )
    ).scalar_one_or_none()

    if existing:
        raise BusinessException(message="实验设备已存在")

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
        raise BusinessException(message="实验设备不存在")

    payload = payload.model_dump(exclude_none=True)
    lab_id = payload.get("lab_id", equipment.lab_id)
    name = payload.get("name", equipment.name)
    lab = db.execute(select(Lab).where(Lab.id == lab_id))
    if not lab:
        raise BusinessException(message="实验室不存在")

    existing = db.execute(
        select(Equipment).where(
            Equipment.lab_id == lab_id,
            Equipment.name == name,
            Equipment.id != equipment.id,
        )
    ).scalar_one_or_none()
    if existing:
        raise BusinessException(message="同一个实验室不能存在同名设备")

    for filed, value in payload.items():
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
        raise BusinessException(message="实验设备不存在")
    db.delete(equipment)
    db.commit()
