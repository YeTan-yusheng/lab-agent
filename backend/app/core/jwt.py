from datetime import datetime, timedelta, timezone
import jwt
from app.config import settings


def create_access_token(user_id: int, token_version) -> str:
    """创建访问令牌"""
    now = datetime.now(timezone.utc)  # 时间以本地时区时间为主
    payload = {
        "user_id": user_id,
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expire_hours),
    }

    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=settings.jwt_algorithm,
        options={"require": ["exp", "iat", "user_id", "ver"]},
    )
