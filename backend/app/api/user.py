from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models.user import User
from app.dependencies.auth import get_current_user
from app.core.response import Response
from app.services import user_service
from app.schemas.user import UserUpdateRequest
from app.core.database import get_db

router = APIRouter(prefix="/user", tags=["用户信息接口"])


@router.get("/info")
def get_user_info(current_user: User = Depends(get_current_user)):
    return Response.success(data=user_service.get_user_info(current_user))


@router.put("/update")
def update_user_info(
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = user_service.update_user_info(db, current_user, payload)
    return Response.success(data=result)