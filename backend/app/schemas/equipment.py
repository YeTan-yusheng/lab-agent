from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class EquipmentResponse(BaseModel):
    id: int
    lab_id: int
    lab_name: str | None = None
    name: str
    description: str | None = None
    img: str | None = None
    spec: str | None = None
    quantity: int
    status: int

    model_config = ConfigDict(from_attributes=True)


class EquipmentDetailResponse(EquipmentResponse):
    lab_status: int | None = None


class EquipmentCreateRequest(BaseModel):
    lab_id: int
    name: str = Field(..., max_length=50)
    description: str | None = Field(
        default=None, max_length=500, description="设备说明"
    )
    img: str | None = Field(None, max_length=200, description="设备图片")
    spec: str | None = Field(None, max_length=100, description="设备型号规格")
    quantity: int = Field(default=1, ge=1, description="设备数量，必须大于等于1")
    status: Literal[0, 1] = 1


class EquipmentUpdateRequest(BaseModel):
    lab_id: int | None = None
    name: str | None = Field(default=None, max_length=50, description="设备名称")
    description: str | None = Field(
        default=None, max_length=500, description="设备说明"
    )
    img: str | None = Field(None, max_length=200, description="设备图片")
    spec: str | None = Field(None, max_length=100, description="设备型号规格")
    quantity: Annotated[
        int | None, Field(ge=1, description="设备数量，必须大于等于1")
    ] = None
    status: Literal[0, 1] | None = None
