from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import LoginRequest
from app.core.database import get_db
from app.core.password import verify_password
from app.schemas.user import UserResponse
from app.core.jwt import create_access_token

router = APIRouter(prefix="/api/auth", tags=["权限验证"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):

    user = db.scalar(select(User).where(User.username == payload.username))

    if user is None or not verify_password(payload.password, user.password):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if user.status != 1:
        raise HTTPException(status_code=401, detail="账号已被禁用")

    token = create_access_token(user.id)

    return {
        "code": 200,
        "messages": "登录成功",
        "data": {"token": token, "user": UserResponse.model_validate(user)},
    }
