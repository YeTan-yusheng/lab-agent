from fastapi import Depends, Request, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User
from app.core.jwt import decode_access_token
from app.core.permissions import (
    RoleProfile,
    get_role_profile,
    validate_roles,
    RoleValidationError,
    Capability,
)
from app.schemas.reservation import ReservationCreateRequest
from app.core.permissions import booking_capability

oauth_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    request: Request, token: str = Depends(oauth_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="登录已失效请重新登录")

    user_id = payload.get("user_id")
    ver = payload.get("ver")

    if user_id is None or ver is None or not isinstance(ver, int):
        raise HTTPException(status_code=401, detail="无效的登录验证")

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user.status != 1:
        raise HTTPException(status_code=401, detail="用户已被禁用")
    if user.token_version != ver:
        raise HTTPException(status_code=401, detail="登录已失效请重新登录")

    try:
        role_profile = get_role_profile(user)
    except RoleValidationError as e:
        raise HTTPException(status_code=403, detail="非法的角色")
    request.state.role_profile = role_profile

    return user


def require_capability(capability: Capability):
    """检查当前用户是否具有此能力"""

    def _checker_capability(
        request: Request, current_user: User = Depends(get_current_user)
    ):
        profile: RoleProfile = request.state.role_profile or get_role_profile(
            current_user
        )
        if not profile.has(capability):
            raise HTTPException(status_code=403, detail="无权限访问")
        return current_user

    return _checker_capability


def require_booking_capability(
    request: Request,
    payload: ReservationCreateRequest,
    current_user: User = Depends(get_current_user),
) -> User:
    """检查预约能力"""
    profile: RoleProfile = request.state.role_profile
    required = booking_capability(payload.equipment_id)
    if not profile.has(required):
        raise HTTPException(status_code=403, detail="无权限预约该类型资源")
    return current_user
