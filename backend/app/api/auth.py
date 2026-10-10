from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.core.database import get_db
from app.core.password import verify_password
from app.schemas.user import UserResponse
from app.core.jwt import create_access_token
from app.core.exceptions import BusinessException
from app.core.response import Response

router = APIRouter(prefix="/api/auth", tags=["权限验证"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):

    user = db.scalar(select(User).where(User.username == payload.username))

    if not user or not verify_password(payload.password, user.password):
        raise BusinessException(code=401, message="账号或密码错误")
    # 验证账号的状态
    if user.status != 1:
        raise BusinessException(code=401, message="账号被禁用")
    # 创建token
    token = create_access_token(user.id)
    # 返回信息
    return Response.success(
        message="登录成功",
        data=LoginResponse(token=token, user=UserResponse.model_validate(user)),
    )
