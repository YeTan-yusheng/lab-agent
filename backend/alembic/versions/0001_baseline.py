"""baseline: existing users/labs/equipments/reservations

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-02
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


MYSQL_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column("username", sa.String(length=50), nullable=False, comment="账号"),
        sa.Column("password", sa.String(length=100), nullable=False, comment="密码"),
        sa.Column("name", sa.String(length=50), nullable=False, comment="名称"),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            comment="角色: student-学生，admin-管理员",
        ),
        sa.Column("email", sa.String(length=100), nullable=True, comment="邮箱"),
        sa.Column("phone", sa.String(length=20), nullable=True, comment="手机号"),
        sa.Column("avatar", sa.String(length=200), nullable=True, comment="头像"),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            comment="状态: 1-启用，0-禁用",
        ),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        **MYSQL_OPTIONS,
    )

    op.create_table(
        "labs",
        sa.Column(
            "id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column("name", sa.String(length=50), nullable=False, comment="实验室名称"),
        sa.Column("location", sa.String(length=100), nullable=True, comment="位置"),
        sa.Column("capacity", sa.Integer(), nullable=False, comment="容纳人数"),
        sa.Column(
            "open_time", sa.String(length=20), nullable=True, comment="开放开始时间"
        ),
        sa.Column(
            "close_time", sa.String(length=20), nullable=True, comment="开放结束时间"
        ),
        sa.Column("description", sa.String(length=500), nullable=True, comment="简介"),
        sa.Column("img", sa.String(length=200), nullable=True, comment="封面图"),
        sa.Column(
            "status", sa.Integer(), nullable=False, comment="状态：0-关闭，1-开放"
        ),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        comment="实验室信息表",
        **MYSQL_OPTIONS,
    )

    op.create_table(
        "equipments",
        sa.Column(
            "id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column("lab_id", sa.Integer(), nullable=False, comment="所属实验室"),
        sa.Column("name", sa.String(length=50), nullable=False, comment="设备名称"),
        sa.Column("description", sa.String(length=500), nullable=True, comment="说明"),
        sa.Column("img", sa.String(length=200), nullable=True, comment="图片"),
        sa.Column("spec", sa.String(length=100), nullable=True, comment="型号规格"),
        sa.Column("quantity", sa.Integer(), nullable=False, comment="数量"),
        sa.Column(
            "status", sa.Integer(), nullable=False, comment="状态：0-维修，1-正常"
        ),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["lab_id"],
            ["labs.id"],
            name="fk_equipments_lab_id",
        ),
        comment="实验室设备表",
        **MYSQL_OPTIONS,
    )

    op.create_table(
        "reservations",
        sa.Column(
            "id", sa.Integer(), autoincrement=True, nullable=False, comment="主键ID"
        ),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="预约人"),
        sa.Column("lab_id", sa.Integer(), nullable=False, comment="实验室"),
        sa.Column(
            "equipment_id",
            sa.Integer(),
            nullable=True,
            comment="设备，空表示预约实验室",
        ),
        sa.Column("date", sa.String(length=20), nullable=False, comment="预约日期"),
        sa.Column("start_time", sa.String(length=20), nullable=False, comment="开始时间"),
        sa.Column("end_time", sa.String(length=20), nullable=False, comment="结束时间"),
        sa.Column("remark", sa.String(length=255), nullable=True, comment="备注"),
        sa.Column(
            "status",
            sa.Integer(),
            nullable=False,
            comment="预约状态 0待审核，1已通过，2已拒绝，3已取消",
        ),
        sa.Column("create_time", sa.DateTime(), nullable=False, comment="创建时间"),
        sa.Column("update_time", sa.DateTime(), nullable=False, comment="更新时间"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_reservations_user_id",
        ),
        sa.ForeignKeyConstraint(
            ["lab_id"],
            ["labs.id"],
            name="fk_reservations_lab_id",
        ),
        sa.ForeignKeyConstraint(
            ["equipment_id"],
            ["equipments.id"],
            name="fk_reservations_equipment_id",
        ),
        comment="预约信息",
        **MYSQL_OPTIONS,
    )


def downgrade() -> None:
    op.drop_table("reservations")
    op.drop_table("equipments")
    op.drop_table("labs")
    op.drop_table("users")