from sqlalchemy.orm import Session

from app.schemas.user import UserResponse
from app.models.user import User
from app.schemas.user import UserUpdateRequest, PasswordUpdateRequest
from app.core.password import verify_password, hash_password
from app.core.exceptions import BusinessException


def get_user_info(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


def update_user_info(db: Session, user: User, payload: UserUpdateRequest):
    user_dict = payload.model_dump(exclude_none=True)
    for field, value in user_dict.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


def update_password(db: Session, user: User, payload: PasswordUpdateRequest):
    if not verify_password(payload.old_password, user.password):
        raise BusinessException(message="原密码错误")
    if payload.new_password == payload.old_password:
        raise BusinessException(message="新密码不能与原密码相同")

    user.password = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
