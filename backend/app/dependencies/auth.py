from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User
from app.core.jwt import decode_access_token
from app.core.exceptions import BusinessException

oauth_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="登录已失效请重新登录")

    user_id = payload.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="无效的登录验证")

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.status != 1:
        raise HTTPException(status_code=401, detail="用户已被禁用")

    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise BusinessException(message="无权限访问", code=403)
    return current_user
