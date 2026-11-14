import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

TIME_PATTERN = r"^(?:[01]\d|2[0-3]):[0-5]\d$"
DATE_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"


class LabResponse(BaseModel):
    id: int
    name: str
    location: str | None = None
    capacity: int
    open_time: str | None = None
    close_time: str | None = None
    description: str | None = None
    img: str | None = None
    status: int

    model_config = ConfigDict(from_attributes=True)


class LabClosedDayResponse(BaseModel):
    lab_id: int
    date: datetime.date
    reason: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LabDetailResponse(LabResponse):
    closed_days: list[LabClosedDayResponse] = Field(default_factory=list)


class LabCreateRequest(BaseModel):
    name: str = Field(..., max_length=50, description="实验室名称")
    location: str | None = Field(default=None, max_length=100, description="实验室位置")
    capacity: int = Field(default=1, ge=1, description="实验室容纳人数，必须大于等于1")
    open_time: str = Field(
        default="08:00",
        pattern=TIME_PATTERN,
        description="实验室开放时间，格式为HH:MM",
    )
    close_time: str = Field(
        default="18:00",
        pattern=TIME_PATTERN,
        description="实验室关闭时间，格式为HH:MM",
    )
    description: str | None = Field(
        default=None, max_length=500, description="实验室简介"
    )
    img: str | None = Field(None, max_length=200, description="实验室图片")
    status: Literal[0, 1] = 1


class LabUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=50, description="实验室名称")
    location: str | None = Field(default=None, max_length=100, description="实验室位置")
    capacity: Annotated[
        int | None, Field(ge=1, description="实验室容纳人数，必须大于等于1")
    ] = None
    open_time: Annotated[
        str | None,
        Field(pattern=TIME_PATTERN, description="格式为 HH:MM"),
    ] = None
    close_time: Annotated[
        str | None,
        Field(pattern=TIME_PATTERN, description="格式为 HH:MM"),
    ] = None
    description: str | None = Field(
        default=None, max_length=500, description="实验室简介"
    )
    img: str | None = Field(None, max_length=200, description="实验室图片")
    status: Literal[0, 1] | None = None


class LabClosedDayRequest(BaseModel):
    date: datetime.date
    reason: str | None = Field(default=None, max_length=255, description="关闭原因")
