import datetime
from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.response import Response
from app.core.database import get_db
from app.dependencies.auth import require_capability, get_current_user
from app.models.user import User
from app.schemas.lab import LabClosedDayRequest, LabCreateRequest, LabUpdateRequest
from app.services import lab_service
from app.core.permissions import Capability

router = APIRouter(prefix="/lab", tags=["实验室管理"])


@router.get("/list")
def get_lab_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    keywords: str | None = None,
    status: int | None = Query(default=None, ge=0, le=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = lab_service.get_labs_page_list(db, page, page_size, keywords, status)
    return Response.success(data=res)


@router.get("/{lab_id}/closed_days")
def get_lab_closed_days(
    lab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = lab_service.get_lab_closed_days(db, lab_id)
    return Response.success(data=res)


@router.get("/{lab_id}")
def get_lab(
    lab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = lab_service.get_lab(db, lab_id)
    return Response.success(data=res)


@router.post("")
def create_lab(
    payload: LabCreateRequest,
    current_user: User = Depends(require_capability(Capability.manage_resources)),
    db: Session = Depends(get_db),
):
    res = lab_service.create_lab(db, payload)
    return Response.success(data=res)


@router.put("/{lab_id}/closed_day")
def update_lab_closed_day(
    lab_id: int,
    payload: LabClosedDayRequest,
    current_user: User = Depends(require_capability(Capability.manage_resources)),
    db: Session = Depends(get_db),
):
    res = lab_service.update_lab_closed_day(db, lab_id, payload)
    return Response.success(data=res)


@router.put("/{lab_id}")
def update_lab(
    lab_id: int,
    payload: LabUpdateRequest,
    current_user: User = Depends(require_capability(Capability.manage_resources)),
    db: Session = Depends(get_db),
):
    res = lab_service.update_lab(db, lab_id, payload)
    return Response.success(data=res)


@router.delete("/{lab_id}/closed_days")
def delete_lab_closed_day(
    lab_id: int,
    date: datetime.date,
    current_user: User = Depends(require_capability(Capability.manage_resources)),
    db: Session = Depends(get_db),
):
    lab_service.delete_lab_closed_day(db, lab_id, date)
    return Response.success(message="删除成功")


@router.delete("/{lab_id}")
def delete_lab(
    lab_id: int,
    current_user: User = Depends(require_capability(Capability.manage_resources)),
    db: Session = Depends(get_db),
):
    lab_service.delete_lab(db, lab_id)
    return Response.success(message="删除成功")
