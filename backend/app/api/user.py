from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.models.user import User
from app.dependencies.auth import require_capability, get_current_user
from app.core.response import Response
from app.services import user_service
from app.schemas.user import (
    RolesUpdateRequest,
    UserUpdateRequest,
    PasswordUpdateRequest,
    UserCreateRequest,
)
from app.core.database import get_db
from app.core.permissions import Capability

router = APIRouter(prefix="/user", tags=["用户信息接口"])


@router.get("/me")
def get_user_info(current_user: User = Depends(get_current_user)):
    return Response.success(data=user_service.get_user_info(current_user))


@router.put("/me")
def update_user_info(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = user_service.update_user_info(db, current_user, payload)
    return Response.success(data=result)


@router.put("/password")
def update_password(
    payload: PasswordUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_service.update_password(db, current_user, payload)
    return Response.success()


@router.get("/list")
def get_user_list(
    page: int = 1,
    page_size: int = 10,
    keywords: str | None = None,
    current_user: User = Depends(require_capability(Capability.manage_users)),
    db: Session = Depends(get_db),
):
    res = user_service.get_user_page_list(db, page, page_size, keywords)
    return Response.success(data=res)


@router.get("/{user_id}")
def get_user_detail(
    user_id: int,
    current_user: User = Depends(require_capability(Capability.manage_users)),
    db: Session = Depends(get_db),
):
    res = user_service.get_user_detail(db, user_id)
    return Response.success(data=res)


@router.post("")
def create_user(
    request: Request,
    payload: UserCreateRequest,
    current_user: User = Depends(require_capability(Capability.manage_users)),
    db: Session = Depends(get_db),
):
    res = user_service.create_user(request, db, payload, current_user)
    return Response.success(data=res)


@router.put("/{user_id}/roles")
def update_user_roles(
    request: Request,
    payload: RolesUpdateRequest,
    user_id: int,
    current_user: User = Depends(require_capability(Capability.manage_users)),
    db: Session = Depends(get_db),
):
    """更新用户角色"""
    res = user_service.update_user_roles(request, db, current_user, user_id, payload)
    return Response.success(data=res)


@router.put("/{user_id}")
def update_user(
    request: Request,
    payload: UserUpdateRequest,
    user_id: int,
    current_user: User = Depends(require_capability(Capability.manage_users)),
    db: Session = Depends(get_db),
):
    """更新用户信息"""
    res = user_service.update_user(request, db, user_id, payload, current_user)
    return Response.success(data=res)


@router.delete("/{user_id}")
def delete_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_capability(Capability.manage_users)),
    db: Session = Depends(get_db),
):
    user_service.delete_user(request, db, user_id, current_user)
    return Response.success()
