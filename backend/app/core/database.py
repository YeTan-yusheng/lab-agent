from sqlalchemy import create_engine, make_url
from sqlalchemy.orm import sessionmaker
from app.config import settings

backend = make_url(settings.database_url).get_backend_name()
kwargs = {"isolation_level": "READ COMMITTED"} if backend == "mysql" else {}
engine = create_engine(settings.database_url, **kwargs)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
