from app.models.base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import CheckConstraint, Index, String, ForeignKey, UniqueConstraint


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"comment": "用户信息表"}

    username: Mapped[str] = mapped_column(String(50), comment="账号", nullable=False)
    password: Mapped[str] = mapped_column(String(100), comment="密码", nullable=False)
    name: Mapped[str] = mapped_column(String(50), comment="名称", nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), comment="角色: student-学生，admin-管理员", nullable=False
    )
    email: Mapped[str | None] = mapped_column(String(100), comment="邮箱")
    phone: Mapped[str | None] = mapped_column(String(20), comment="手机号")
    avatar: Mapped[str | None] = mapped_column(String(200), comment="头像")
    status: Mapped[int] = mapped_column(
        default=1, comment="状态: 1-启用，0-禁用", nullable=False
    )
    token_version: Mapped[int] = mapped_column(default=0, comment="token版本号")
    roles: Mapped[list["UserRoles"]] = relationship(
        back_populates="user",
        lazy="selectin",
        cascade="all,delete-orphan",
        passive_deletes=True,
    )


class UserRoles(Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_code", name="uq_user_roles_user_role"),
        Index("ix_user_roles_role_code", "role_code"),
        CheckConstraint(
            "role_code IN ('student', 'teacher', 'admin')",
            name="ck_user_roles_role_code",
        ),
        {"comment": "用户角色表"},
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(User.id, ondelete="CASCADE"), comment="用户ID", nullable=False
    )
    role_code: Mapped[str] = mapped_column(
        String(20), comment="角色编码", nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="roles")
