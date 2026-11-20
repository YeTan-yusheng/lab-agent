from datetime import datetime
from typing import Self
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AvailabilityRequest(BaseModel):
    lab_id: int
    equipment_id: int | None = None
    date: str
    start_time: str
    end_time: str

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        try:
            return datetime.strptime(v, "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise ValueError("日期格式必须为 YYYY-MM-DD")

    @field_validator("start_time", "end_time")
    @classmethod
    def _check_time(cls, v: str) -> str:
        try:
            return datetime.strptime(v, "%H:%M").time().strftime("%H:%M")
        except ValueError:
            raise ValueError("时间格式必须为 HH:MM")

    @model_validator(mode="after")
    def _check_order(self) -> Self:
        if self.start_time >= self.end_time:
            raise ValueError("结束时间必须晚于开始时间")
        return self


class ReservationCreateRequest(AvailabilityRequest):
    remark: str | None = Field(default=None, max_length=255, description="预约备注")


class ReservationResponse(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    lab_id: int
    lab_name: str | None = None
    equipment_id: int | None = None
    equipment_name: str | None = None
    type: str | None = None
    date: str
    start_time: str
    end_time: str
    remark: str | None = None
    status: int
    model_config = ConfigDict(from_attributes=True)


class AuditReservationRequest(BaseModel):
    status: int  # 只能是 1 通过 或 2 不通过


class ConflictInfo(BaseModel):
    reservation_id: int
    type: str  # lab或equipment
    start_time: str
    end_time: str


class AvailabilityResponse(BaseModel):
    available: bool
    reason_code: str | None = None
    message: str | None = None
    conflicts: list[ConflictInfo] = Field(default_factory=list)
    http_status: int = 200
