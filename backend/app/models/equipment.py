from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from app.models.base import Base
from app.models.lab import Lab


class Equipment(Base):
    __tablename__ = "equipments"
    __table_args__ = (
        UniqueConstraint("lab_id", "name", name="uq_equipment_lab_name"),
        CheckConstraint(
            "status IN (0,1) AND quantity >= 1", name="ck_equipment_status_and_quantity"
        ),
        Index("ix_equipments_lab_id", "lab_id"),
        {"comment": "实验室设备表"},
    )

    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id"), nullable=False, comment="所属实验室"
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="设备名称")
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="说明"
    )
    img: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="图片")
    spec: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="型号规格"
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, comment="数量")
    status: Mapped[int] = mapped_column(default=1, comment="状态：0-维修，1-正常")

    lab: Mapped[Lab] = relationship()
