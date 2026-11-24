from datetime import datetime
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.user import User


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN (0, 1, 2, 3, 4)",
            name="ck_reservations_status",
        ),
        Index(
            "ix_reservations_lab_date_status",
            "lab_id",
            "date",
            "status",
        ),
        Index(
            "ix_reservations_equipment_date_status",
            "equipment_id",
            "date",
            "status",
        ),
        Index(
            "ix_reservations_user_status_id",
            "user_id",
            "status",
            "id",
        ),
        Index(
            "ix_reservations_status_date_start",
            "status",
            "date",
            "start_time",
        ),
        {"comment": "预约信息"},
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), comment="预约人", nullable=False
    )
    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id"), comment="实验室", nullable=False
    )
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("equipments.id"), comment="设备，空表示预约实验室", nullable=True
    )
    date: Mapped[str] = mapped_column(String(20), comment="预约日期", nullable=False)
    start_time: Mapped[str] = mapped_column(
        String(20), comment="开始时间", nullable=False
    )
    end_time: Mapped[str] = mapped_column(
        String(20), comment="结束时间", nullable=False
    )
    remark: Mapped[str] = mapped_column(String(255), comment="备注", nullable=True)
    status: Mapped[int] = mapped_column(
        comment="预约状态 0待审核，1已通过，2已拒绝，3已取消，4已过期",
        default=0,
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), comment="审核人", nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="审核时间", nullable=True
    )
    reject_reason: Mapped[str | None] = mapped_column(
        String(255), comment="拒绝原因", nullable=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(
        String(255), comment="取消原因", nullable=True
    )
    cancelled_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), comment="取消操作人", nullable=True
    )
    self_audit: Mapped[bool] = mapped_column(
        Boolean,
        comment="是否通过自审通过",
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    lab: Mapped[Lab] = relationship()
    equipment: Mapped[Equipment] = relationship()
