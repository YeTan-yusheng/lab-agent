from pydantic import BaseModel

from app.schemas.user import CurrentUserResponse


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: CurrentUserResponse


class RegisterRequest(BaseModel):
    username: str
    password: str
    name: str | None = None
