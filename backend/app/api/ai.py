from fastapi import APIRouter, Depends

from app.core.response import Response
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai import ChatMessage, ChatRequest
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["AI相关的API"])


@router.post("/chat")
def chat(data: ChatRequest, current_user: User = Depends(get_current_user)):
    content = ai_service.chat(data)
    return Response.success(data=ChatMessage(role="assistant", content=content))
