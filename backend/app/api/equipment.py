from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.response import Response
from app.dependencies.auth import get_current_user, require_capability
from app.schemas.equipment import (
    EquipmentCreateRequest,
    EquipmentUpdateRequest,
)
from app.services import equipment_service
from app.core.database import get_db
from app.core.permissions import Capability
from app.models.user import User

router = APIRouter(prefix="/equipment", tags=["实验室设备信息接口"])


@router.get("/list")
def get_equipment_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    keywords: str | None = None,
    lab_id: int | None = None,
    status: int | None = Query(default=None, ge=0, le=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = equipment_service.get_equipment_page_list(
        db, page, page_size, keywords, lab_id, status
    )
    return Response.success(data=res)


@router.get("/{equipment_id}")
def get_equipment(
    equipment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = equipment_service.get_equipment(db, equipment_id)
    return Response.success(data=res)


@router.post("")
def create_equipment(
    payload: EquipmentCreateRequest,
    current_user: User = Depends(require_capability(Capability.manage_resources)),
    db: Session = Depends(get_db),
):
    res = equipment_service.create_equipment(db, payload)
    return Response.success(data=res)


@router.put("/{equipment_id}")
def update_equipment(
    equipment_id: int,
    payload: EquipmentUpdateRequest,
    current_user: User = Depends(require_capability(Capability.manage_resources)),
    db: Session = Depends(get_db),
):
    res = equipment_service.update_equipment(db, equipment_id, payload)
    return Response.success(data=res)


@router.delete("/{equipment_id}")
def delete_equipment(
    equipment_id: int,
    current_user: User = Depends(require_capability(Capability.manage_resources)),
    db: Session = Depends(get_db),
):
    equipment_service.delete_equipment(db, equipment_id)
    return Response.success(message="删除成功")
