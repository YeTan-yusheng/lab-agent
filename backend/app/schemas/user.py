from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    id: int
    username: str
    name: str
    role: str
    phone: str | None = None
    email: str | None = None
    avatar: str | None = None
    status: int

    model_config = ConfigDict(from_attributes=True)


class CurrentUserResponse(UserResponse):
    roles: list[str]
    capabilities: list[str]
    primary_role: str
    display_name: str


class UserCreateRequest(BaseModel):
    username: str
    password: str = "123456"
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    avatar: str | None = None
    role: str = "student"
    status: int = 1


class UserUpdateRequest(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    avatar: str | None = None
    role: str | None = None
    status: int | None = None


class PasswordUpdateRequest(BaseModel):
    old_password: str
    new_password: str
