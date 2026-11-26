from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.reservation import Reservation
from app.models.user import User


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_notifications_dedupe_key"),
        Index(
            "ix_notifications_user_read_id",
            "user_id",
            "is_read",
            "id",
        ),
        Index(
            "ix_notifications_user_id_id",
            "user_id",
            "id",
        ),
        Index(
            "ix_notifications_reservation_id",
            "reservation_id",
            "id",
        ),
        {"comment": "站内信"},
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_notifications_user_id"),
        comment="接收人",
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(40), comment="通知类型", nullable=False)
    title: Mapped[str] = mapped_column(String(100), comment="标题", nullable=False)
    content: Mapped[str] = mapped_column(String(500), comment="正文", nullable=False)
    reservation_id: Mapped[int | None] = mapped_column(
        ForeignKey("reservations.id", name="fk_notifications_reservation_id"),
        comment="预约ID",
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        comment="是否已读",
        nullable=False,
        default=False,
        server_default=text("0"),
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="已读时间", nullable=True
    )
    dedupe_key: Mapped[str] = mapped_column(
        String(128), comment="幂等键", nullable=False
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    reservation: Mapped[Reservation | None] = relationship(
        foreign_keys=[reservation_id]
    )
