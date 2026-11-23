from sqlalchemy import create_engine, make_url
from sqlalchemy.orm import sessionmaker
from app.config import settings

backend = make_url(settings.database_url).get_backend_name()

kwargs = {"hide_parameters": True}
if backend == "mysql":
    kwargs["isolation_level"] = "READ COMMITTED"
engine = create_engine(settings.database_url, **kwargs)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
