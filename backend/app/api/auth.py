from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.auth import LoginRequest, RegisterRequest
from app.core.database import get_db
from app.core.response import Response
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["权限验证"])


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    result = auth_service.verify_login(db, payload)
    return Response.success(message="登录成功", data=result)


@router.post("/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    auth_service.register(db, payload)
    return Response.success(message="注册成功")
