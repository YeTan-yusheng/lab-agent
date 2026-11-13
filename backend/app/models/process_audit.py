from enum import StrEnum

from sqlalchemy import Index, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ActionType(StrEnum):
    create_user = "create_user"
    update_roles = "update_roles"
    disable_user = "disable_user"
    enable_user = "enable_user"
    delete_user = "delete_user"
    reset_password = "reset_password"


class ProcessAudit(Base):
    __tablename__ = "process_audit"
    __table_args__ = (
        Index("idx_actor_user_create_time", "actor_user_id", "create_time"),
        Index("idx_target_user_create_time", "target_user_id", "create_time"),
        Index("request_id", "request_id"),
        Index("idx_action_create_time", "action", "create_time"),
        {"comment": "流程审核表"},
    )

    actor_user_id: Mapped[int] = mapped_column(comment="操作人ID", nullable=False)
    target_user_id: Mapped[int] = mapped_column(comment="目标用户ID", nullable=False)
    action: Mapped[ActionType] = mapped_column(
        SAEnum(
            ActionType,
            name="action_type_enum",
            native_enum=False,
            validate_strings=True,
        ),
        comment="操作类型",
        nullable=False,
    )
    old_roles: Mapped[str | None] = mapped_column(
        String(50), comment="排序后的旧角色数组"
    )
    new_roles: Mapped[str | None] = mapped_column(
        String(50), comment="排序后的新角色数组"
    )
    result: Mapped[str] = mapped_column(
        String(10), comment="success/failed", nullable=False
    )
    error_code: Mapped[str | None] = mapped_column(String(64), comment="错误码")
    request_id: Mapped[str] = mapped_column(
        String(64), comment="请求ID", nullable=False
    )
    ip: Mapped[str | None] = mapped_column(String(45), comment="操作来源")
    user_agent: Mapped[str | None] = mapped_column(String(255), comment="用户代理")


class AgentToolCallingAudit(Base):
    __tablename__ = "agent_tool_calling_audit"
    __table_args__ = (
        Index("idx_user_create_time", "user_id", "create_time"),
        Index("idx_tool_create_time", "tool_name", "create_time"),
        {"comment": "AI工具调用审计表"},
    )

    user_id: Mapped[int] = mapped_column(comment="调用用户ID", nullable=False)
    roles: Mapped[str] = mapped_column(String(50), comment="用户角色", nullable=False)
    capability: Mapped[str] = mapped_column(
        String(50), comment="用户能力", nullable=False
    )
    tool_name: Mapped[str] = mapped_column(
        String(50), comment="调用工具名称", nullable=False
    )
    result: Mapped[str] = mapped_column(
        String(10), comment="success/failed", nullable=False
    )
    error_code: Mapped[str | None] = mapped_column(String(64), comment="错误码")
    request_id: Mapped[str] = mapped_column(
        String(64), comment="请求ID", nullable=False
    )
