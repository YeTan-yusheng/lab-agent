from datetime import datetime, timedelta
import jwt
from app.config import settings


def create_access_token(user_id: int) -> str:
    expire = datetime.now() + timedelta(hours=settings.jwt_expire_hours)

    payload = {"user_id": user_id, "exp": expire}

    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=settings.jwt_algorithm)
