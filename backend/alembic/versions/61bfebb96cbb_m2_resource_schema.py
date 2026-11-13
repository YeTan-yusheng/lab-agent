"""m2 resource schema

Revision ID: 61bfebb96cbb
Revises: 2c0954a9fdac
Create Date: 2026-11-13 21:57:23.036097

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "61bfebb96cbb"
down_revision: Union[str, Sequence[str], None] = "2c0954a9fdac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _check_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_check_constraints(table_name)}


def _unique_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    """Upgrade schema."""
    if "lab_closed_days" not in _table_names():
        op.create_table(
            "lab_closed_days",
            sa.Column(
                "id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"
            ),
            sa.Column("lab_id", sa.Integer(), nullable=False, comment="实验室ID"),
            sa.Column(
                "date", sa.Date(), nullable=False, comment="关闭日期，格式YYYY-MM-DD"
            ),
            sa.Column(
                "reason", sa.String(length=255), nullable=True, comment="关闭原因"
            ),
            sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
            sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
            sa.ForeignKeyConstraint(
                ["lab_id"],
                ["labs.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("lab_id", "date", name="uq_lab_closed_days_lab_date"),
            comment="实验室关闭日期表",
        )
    if "uq_equipment_lab_name" not in _unique_names("equipments"):
        op.create_unique_constraint(
            "uq_equipment_lab_name", "equipments", ["lab_id", "name"]
        )
    op.alter_column(
        "labs",
        "open_time",
        existing_type=mysql.VARCHAR(
            charset="utf8mb4", collation="utf8mb4_unicode_ci", length=20
        ),
        type_=sa.String(length=5),
        comment="开放开始时间 HH:MM",
        existing_comment="开放开始时间",
        existing_nullable=True,
    )
    op.alter_column(
        "labs",
        "close_time",
        existing_type=mysql.VARCHAR(
            charset="utf8mb4", collation="utf8mb4_unicode_ci", length=20
        ),
        type_=sa.String(length=5),
        comment="开放结束时间 HH:MM",
        existing_comment="开放结束时间",
        existing_nullable=True,
    )
    if "uq_labs_name" not in _unique_names("labs"):
        op.create_unique_constraint("uq_labs_name", "labs", ["name"])

    reservation_indexes = _index_names("reservations")
    for name, columns in (
        (
            "ix_reservations_lab_date_status",
            ["lab_id", "date", "status"],
        ),
        (
            "ix_reservations_equipment_date_status",
            ["equipment_id", "date", "status"],
        ),
    ):
        if name not in reservation_indexes:
            op.create_index(name, "reservations", columns, unique=False)

    for name in (
        "idx_reservations_lab_id",
        "idx_reservations_equipment_id",
    ):
        if name in reservation_indexes:
            op.drop_index(name, table_name="reservations")

    lab_checks = _check_names("labs")
    if "ck_lab_status_and_capacity" not in lab_checks:
        op.create_check_constraint(
            "ck_lab_status_and_capacity",
            "labs",
            "status IN (0,1) AND capacity >= 1",
        )

    equipment_checks = _check_names("equipments")
    if "ck_equipment_status_and_quantity" not in equipment_checks:
        op.create_check_constraint(
            "ck_equipment_status_and_quantity",
            "equipments",
            "status IN (0,1) AND quantity >= 1",
        )


def downgrade() -> None:
    """Downgrade schema."""
    reservation_indexes = _index_names("reservations")
    for name, columns in (
        ("idx_reservations_lab_id", ["lab_id"]),
        ("idx_reservations_equipment_id", ["equipment_id"]),
    ):
        if name not in reservation_indexes:
            op.create_index(name, "reservations", columns, unique=False)

    for name in (
        "ix_reservations_lab_date_status",
        "ix_reservations_equipment_date_status",
    ):
        if name in reservation_indexes:
            op.drop_index(name, table_name="reservations")

    lab_checks = _check_names("labs")
    if "ck_lab_status_and_capacity" in lab_checks:
        op.drop_constraint("ck_lab_status_and_capacity", "labs", type_="check")

    equipment_checks = _check_names("equipments")
    if "ck_equipment_status_and_quantity" in equipment_checks:
        op.drop_constraint(
            "ck_equipment_status_and_quantity", "equipments", type_="check"
        )

    op.drop_constraint("uq_labs_name", "labs", type_="unique")
    op.alter_column(
        "labs",
        "close_time",
        existing_type=sa.String(length=5),
        type_=mysql.VARCHAR(
            charset="utf8mb4", collation="utf8mb4_unicode_ci", length=20
        ),
        comment="开放结束时间",
        existing_comment="开放结束时间 HH:MM",
        existing_nullable=True,
    )
    op.alter_column(
        "labs",
        "open_time",
        existing_type=sa.String(length=5),
        type_=mysql.VARCHAR(
            charset="utf8mb4", collation="utf8mb4_unicode_ci", length=20
        ),
        comment="开放开始时间",
        existing_comment="开放开始时间 HH:MM",
        existing_nullable=True,
    )

    equipment_indexes = _index_names("equipments")
    if "ix_equipments_lab_id" not in equipment_indexes:
        op.create_index(
            "ix_equipments_lab_id", "equipments", ["lab_id"], unique=False
        )

    op.drop_constraint("uq_equipment_lab_name", "equipments", type_="unique")
    op.drop_table("lab_closed_days")