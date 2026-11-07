from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func, delete

from app.schemas.user import (
    CurrentUserResponse,
    RolesUpdateRequest,
    UserResponse,
    UserCreateRequest,
)
from app.models.user import User, UserRoles
from app.schemas.user import UserUpdateRequest, PasswordUpdateRequest
from app.core.password import verify_password, hash_password
from app.core.exceptions import BusinessException
from app.core.response import PageResponse
from app.core.permissions import Role, RoleProfile, validate_roles, RoleValidationError


def get_user_info(user: User) -> CurrentUserResponse:
    """获取用户信息"""
    return build_current_user(user)


def update_user_info(
    db: Session, user: User, payload: UserUpdateRequest
) -> CurrentUserResponse:
    user_dict = payload.model_dump(exclude_none=True, exclude=["role", "status"])
    for field, value in user_dict.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return build_current_user(user)


def update_password(db: Session, user: User, payload: PasswordUpdateRequest):
    if not verify_password(payload.old_password, user.password):
        raise BusinessException(message="原密码错误")
    if payload.new_password == payload.old_password:
        raise BusinessException(message="新密码不能与原密码相同")

    user.password = hash_password(payload.new_password)
    user.token_version += 1
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

    role_profile: RoleProfile = validate_roles(payload.roles)

    user = User(
        username=payload.username,
        password=hash_password(payload.password),
        name=payload.name or payload.username,
        role=role_profile.primary_role.value,
        email=payload.email,
        phone=payload.phone,
        avatar=payload.avatar,
        status=payload.status,
    )
    db.add(user)
    db.flush()
    db.add_all(
        [
            UserRoles(user_id=user.id, role_code=role.value)
            for role in role_profile.roles
        ]
    )
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


def update_user(db: Session, user_id: int, payload: UserUpdateRequest) -> UserResponse:
    """用户管理更新用户"""
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise BusinessException(message="用户不存在")

    if payload.status == 0:
        ensure_not_last_active_admin(db, user_id)

    new_status = payload.status if user.status != payload.status else None
    data = payload.model_dump(exclude_none=True)

    for filed, value in data.items():
        setattr(user, filed, value)
    if new_status is not None:
        user.token_version += 1
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


def update_user_roles(
    db: Session, current_user: User, user_id: int, payload: RolesUpdateRequest
) -> UserResponse:
    """用户管理-更新用户角色"""
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise BusinessException(message="用户不存在")

    role_profile = validate_roles(payload.roles)
    if user_id == current_user.id:
        raise BusinessException(message="不能更新当前登录的账号角色")

    ensure_not_last_admin(db, user_id, role_profile)

    db.execute(delete(UserRoles).where(UserRoles.user_id == user_id))
    db.add_all(
        [
            UserRoles(user_id=user.id, role_code=role.value)
            for role in role_profile.roles
        ]
    )

    user.role = role_profile.primary_role.value
    user.token_version += 1
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

    ensure_not_last_active_admin(db, user_id)
    db.delete(user)
    db.commit()


def build_current_user(user: User) -> CurrentUserResponse:
    """构建当前用户响应"""
    profile = validate_roles([role.role_code for role in user.roles])
    return CurrentUserResponse(
        **UserResponse.model_validate(user).model_dump(),
        **profile.to_api(),
    )


def ensure_not_last_admin(db: Session, user_id: int, role_profile: RoleProfile):
    # 检查是否会移除除操作者外的最后一个其他管理员角色
    current_roles = [
        role.role_code
        for role in db.execute(
            select(UserRoles).where(UserRoles.user_id == user_id)
        ).scalars()
    ]
    if ("admin" in current_roles) and (
        "admin" not in {r.value for r in role_profile.roles}
    ):
        ensure_not_last_active_admin(db, user_id)


def ensure_not_last_active_admin(db: Session, user_id: int):
    """检查是否会删除最后一个活跃的管理员"""
    lock_last_admin_scope(db, user_id)

    other_admins = db.execute(
        select(func.count(func.distinct(UserRoles.user_id)))
        .join(User, User.id == UserRoles.user_id)
        .where(
            UserRoles.role_code == "admin",
            User.status == 1,
            UserRoles.user_id != user_id,
        )
    ).scalar_one()
    if other_admins == 0:
        raise BusinessException(message="至少保留一个其他管理员角色")


def lock_last_admin_scope(db: Session, target_user_id: int) -> None:
    """锁定最后一个活跃的管理员角色"""
    admin_user_ids = select(UserRoles.user_id).where(UserRoles.role_code == "admin")

    stmt = (
        select(User.id)
        .where(
            or_(
                User.id == target_user_id,
                User.id.in_(admin_user_ids),
            )
        )
        .order_by(User.id)
        .with_for_update()
    )
    db.execute(stmt).scalars().all()
