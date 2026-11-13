from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, UniqueConstraint, CheckConstraint
from app.models.base import Base


class Lab(Base):
    __tablename__ = "labs"
    __table_args__ = (
        UniqueConstraint("name", name="uq_labs_name"),
        CheckConstraint(
            "status IN (0,1) AND capacity >= 1", name="ck_lab_status_and_capacity"
        ),
        {"comment": "实验室信息表"},
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="实验室名称")
    location: Mapped[str | None] = mapped_column(String(100), comment="位置")
    capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="容纳人数"
    )
    open_time: Mapped[str | None] = mapped_column(
        String(5), comment="开放开始时间 HH:MM"
    )
    close_time: Mapped[str | None] = mapped_column(
        String(5), comment="开放结束时间 HH:MM"
    )
    description: Mapped[str | None] = mapped_column(String(500), comment="简介")
    img: Mapped[str | None] = mapped_column(String(200), comment="封面图")
    status: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, comment="状态：0-关闭，1-开放"
    )
