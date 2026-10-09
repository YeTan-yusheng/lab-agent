from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.user import User
from app.schemas.auth import LoginRequest
from app.schemas.user import UserResponse
from app.core.database import get_db

router = APIRouter(prefix="/api/auth", tags=["权限验证"])


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(
        select(User).where(User.username == data.username)
    ).scalar_one_or_none()

    if user is None or user.password != data.password:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    return {
        "code": 200,
        "message": "操作成功",
        "data": UserResponse.model_validate(user),
    }
