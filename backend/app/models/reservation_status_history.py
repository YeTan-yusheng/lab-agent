from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import User


class ReservationStatusHistory(Base):
    __tablename__ = "reservation_status_history"
    __table_args__ = (
        Index(
            "ix_reservation_status_history_reservation_id",
            "reservation_id",
            "id",
        ),
        Index(
            "ix_reservation_status_history_actor_time",
            "actor_id",
            "create_time",
        ),
        Index(
            "ix_reservation_status_history_action_time",
            "action",
            "create_time",
        ),
        {"comment": "预约状态历史"},
    )

    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id"), comment="预约ID", nullable=False
    )
    from_status: Mapped[int | None] = mapped_column(comment="原状态", nullable=True)
    to_status: Mapped[int] = mapped_column(comment="目标状态", nullable=False)
    action: Mapped[str] = mapped_column(
        String(20),
        comment="动作 submit/approve/reject/cancel/force_cancel/expire",
        nullable=False,
    )
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), comment="操作人，系统过期为空", nullable=True
    )
    reason: Mapped[str | None] = mapped_column(
        String(255), comment="拒绝/取消原因", nullable=True
    )
    request_id: Mapped[str] = mapped_column(
        String(64), comment="请求ID", nullable=False
    )

    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id])
