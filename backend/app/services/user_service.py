from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func

from app.schemas.user import UserResponse
from app.models.user import User
from app.schemas.user import UserUpdateRequest, PasswordUpdateRequest
from app.core.password import verify_password, hash_password
from app.core.exceptions import BusinessException
from app.core.response import PageResponse


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


def get_user_page_list(
    db: Session, page: int, page_size: int, keywords: str | None = None
):
    stmt = select(User)
    if keywords:
        stmt = stmt.where(
            or_(User.username.ilike(f"%{keywords}%"), User.name.ilike(f"%{keywords}%"))
        )

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()
    items = db.execute(
        stmt.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars()

    return PageResponse(
        list=[UserResponse.model_validate(item) for item in items], total=total
    )
