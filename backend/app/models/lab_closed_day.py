import datetime

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Date, ForeignKey, String, UniqueConstraint

from app.models.base import Base


class LabClosedDay(Base):
    __tablename__ = "lab_closed_days"
    __table_args__ = (
        UniqueConstraint("lab_id", "date", name="uq_lab_closed_days_lab_date"),
        {"comment": "实验室关闭日期表"},
    )

    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id"), nullable=False, comment="实验室ID"
    )
    date: Mapped[datetime.date] = mapped_column(
        Date, nullable=False, comment="关闭日期，格式YYYY-MM-DD"
    )
    reason: Mapped[str | None] = mapped_column(String(255), comment="关闭原因")
