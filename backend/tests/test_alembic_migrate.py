import pytest
from sqlalchemy import create_engine, text
from app.config import settings


def test_alembic_backfill():
    """测试用户角色回填"""
    e = create_engine(settings.database_url)
    c = e.connect()

    assert c.execute(text("SELECT COUNT(*) FROM users")).scalar() > 0
    assert c.execute(text("SELECT COUNT(*) FROM user_roles")).scalar() > 0
    assert c.execute(
        text("SELECT role_code, COUNT(*) FROM user_roles GROUP BY role_code")
    ).scalar()
    assert (
        c.execute(text("SELECT COUNT(*) FROM users WHERE role IS NULL")).scalar() == 0
    )
    c.close()
    e.dispose()
