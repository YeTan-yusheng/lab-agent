from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func

from app.schemas.user import UserResponse, UserCreateRequest
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
) -> PageResponse:
    """分页模糊查询用户列表"""
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


def create_user(db: Session, payload: UserCreateRequest) -> UserResponse:
    """用户管理新增用户"""
    existing = db.execute(
        select(User).where(User.username == payload.username)
    ).scalar_one_or_none()
    if existing:
        raise BusinessException(message="用户已存在")

    user = User(
        username=payload.username,
        password=hash_password(payload.password),
        name=payload.name or payload.username,
        role=payload.role,
        email=payload.email,
        phone=payload.phone,
        avatar=payload.avatar,
        status=payload.status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


def update_user(db: Session, user_id: int, payload: UserUpdateRequest) -> UserResponse:
    """用户管理更新用户"""
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise BusinessException(message="用户不存在")

    payload = payload.model_dump(exclude_none=True)

    for filed, value in payload.items():
        setattr(user, filed, value)

    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


def delete_user(db: Session, user_id: int, current_user: User):
    """用户管理删除用户"""
    if user_id == current_user.id:
        raise BusinessException(message="不能删除当前登录的账号")

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise BusinessException(message="用户不存在")

    db.delete(user)
    db.commit()
