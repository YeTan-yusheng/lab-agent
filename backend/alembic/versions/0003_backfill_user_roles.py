"""user roles and token version

Revision ID: 0003_backfill_user_roles
Revises: 0002_user_roles_token_version
Create Date: 2026-11-04

"""

# revision identifiers, used by Alembic.
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_backfill_user_roles"
down_revision: Union[str, Sequence[str], None] = "0002_user_roles_token_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

"""
INSERT INTO user_roles (user_id, role_code, create_time, update_time)
SELECT u.id, u.role, NOW(), NOW()
FROM users u
WHERE u.role IN ('student', 'teacher', 'admin')
  AND NOT EXISTS (
      SELECT 1 FROM user_roles ur
      WHERE ur.user_id = u.id
        AND ur.role_code = u.role
  );
"""


def _tables():
    meta = sa.MetaData()
    users = sa.Table(
        "users",
        meta,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("role", sa.String),
    )
    user_roles = sa.Table(
        "user_roles",
        meta,
        sa.Column("user_id", sa.Integer),
        sa.Column("role_code", sa.String),
        sa.Column("create_time", sa.DateTime),
        sa.Column("update_time", sa.DateTime),
    )
    return users, user_roles


def upgrade():
    users, user_roles = _tables()
    conn = op.get_bind()

    now = sa.func.current_timestamp()

    subq = (
        sa.select(
            users.c.id.label("user_id"),
            users.c.role.label("role_code"),
            now.label("create_time"),
            now.label("update_time"),
        )
        .where(users.c.role.in_(("student", "teacher", "admin")))
        .where(
            ~sa.exists().where(
                (user_roles.c.user_id == users.c.id)
                & (user_roles.c.role_code == users.c.role)
            )
        )
    )

    conn.execute(
        user_roles.insert().from_select(
            ["user_id", "role_code", "create_time", "update_time"],
            subq,
        )
    )


def downgrade():
    users, user_roles = _tables()
    conn = op.get_bind()

    subq = sa.select(users.c.id, users.c.role).where(
        users.c.role.in_(("student", "teacher", "admin"))
    )

    conn.execute(
        user_roles.delete().where(
            sa.tuple_(user_roles.c.user_id, user_roles.c.role_code).in_(subq)
        )
    )
