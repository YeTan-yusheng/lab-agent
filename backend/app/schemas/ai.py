from pydantic import BaseModel
from typing import Literal


class ChatMessage(BaseModel):
    role: str = Literal["assistant", "user"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
