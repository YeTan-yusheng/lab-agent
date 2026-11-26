from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.notification import Notification


class EmailOutbox(Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_email_outbox_dedupe_key"),
        CheckConstraint(
            "status IN (0, 1, 2, 3)",
            name="ck_email_outbox_status",
        ),
        CheckConstraint(
            "attempts >= 0",
            name="ck_email_outbox_attempts_nonnegative",
        ),
        CheckConstraint(
            "max_attempts > 0",
            name="ck_email_outbox_max_attempts_positive",
        ),
        Index(
            "ix_email_outbox_status_retry_id",
            "status",
            "next_retry_at",
            "id",
        ),
        Index(
            "ix_email_outbox_to_email_id",
            "to_email",
            "id",
        ),
        Index(
            "ix_email_outbox_notification_id",
            "notification_id",
        ),
        {"comment": "邮件发件箱"},
    )

    notification_id: Mapped[int | None] = mapped_column(
        ForeignKey("notifications.id", name="fk_email_outbox_notification_id"),
        comment="站内信ID",
        nullable=True,
    )
    to_email: Mapped[str] = mapped_column(
        String(255), comment="收件邮箱", nullable=False
    )
    subject: Mapped[str] = mapped_column(
        String(200), comment="邮件主题", nullable=False
    )
    body: Mapped[str] = mapped_column(Text, comment="邮件正文", nullable=False)
    status: Mapped[int] = mapped_column(
        comment="0待发送，1发送中，2已发送，3失败",
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    attempts: Mapped[int] = mapped_column(
        comment="已尝试次数",
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    max_attempts: Mapped[int] = mapped_column(
        comment="最大尝试次数",
        nullable=False,
        default=5,
        server_default=text("5"),
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="下次重试时间", nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(
        String(500), comment="最近失败原因", nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="发送时间", nullable=True
    )
    provider_message_id: Mapped[str | None] = mapped_column(
        String(255), comment="邮件后端消息ID", nullable=True
    )
    dedupe_key: Mapped[str] = mapped_column(
        String(128), comment="幂等键", nullable=False
    )

    notification: Mapped[Notification | None] = relationship(
        foreign_keys=[notification_id]
    )
