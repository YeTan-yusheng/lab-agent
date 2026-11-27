from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationItem(BaseModel):
    id: int
    type: str
    title: str
    content: str
    reservation_id: int | None = None
    is_read: bool
    read_at: datetime | None = None
    create_time: datetime

    model_config = ConfigDict(from_attributes=True)
