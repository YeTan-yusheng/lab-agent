from typing import Literal
from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    id: int
    username: str
    name: str
    role: str
    phone: str | None = None
    email: str | None = None
    avatar: str | None = None
    status: Literal[0, 1] = 1

    model_config = ConfigDict(from_attributes=True)


class CurrentUserResponse(UserResponse):
    roles: list[str]
    capabilities: list[str]
    primary_role: str
    display_name: str


class UserDetailResponse(UserResponse):
    roles: list[str]
    display_name: str


class UserCreateRequest(BaseModel):
    username: str
    password: str = "123456"
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    avatar: str | None = None
    roles: list[str] = ["student"]
    status: Literal[0, 1] = 1


class UserUpdateRequest(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    avatar: str | None = None
    status: Literal[0, 1] | None = None


class RolesUpdateRequest(BaseModel):
    roles: list[str]


class PasswordUpdateRequest(BaseModel):
    old_password: str
    new_password: str
