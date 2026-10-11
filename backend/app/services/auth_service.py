from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
from app.core.password import verify_password
from app.schemas.user import UserResponse
from app.core.jwt import create_access_token
from app.core.exceptions import BusinessException
from app.core.password import hash_password


def verify_login(db: Session, payload: LoginRequest) -> LoginResponse:
    user = db.scalar(select(User).where(User.username == payload.username))

    if not user or not verify_password(payload.password, user.password):
        raise BusinessException(code=401, message="账号或密码错误")
    # 验证账号的状态
    if user.status != 1:
        raise BusinessException(code=401, message="账号被禁用")
    # 创建token
    token = create_access_token(user.id)

    return (LoginResponse(token=token, user=UserResponse.model_validate(user)),)


def register(db: Session, payload: RegisterRequest):
    existing = db.scalar(select(User).where(User.username == payload.username))
    if existing:
        raise BusinessException(code=401, message="账号已经存在")

    user = User(
        username=payload.username,
        password=hash_password(payload.password),
        name=payload.name or payload.username,
        role="student",
        status=1,
    )
    db.add(user)
    db.commit()
    db.flush()
