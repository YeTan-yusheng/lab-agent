from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import Response
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services import notification_service

router = APIRouter(prefix="/notification", tags=["通知"])


@router.get("/list")
def get_notification_list(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    is_read: bool | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = notification_service.get_notification_page_list(
        db,
        current_user,
        page=page,
        page_size=page_size,
        is_read=is_read,
    )
    return Response.success(data=result)


@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = notification_service.get_unread_count(db, current_user)
    return Response.success(data={"count": count})


@router.put("/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = notification_service.mark_all_notifications_read(db, current_user)
    return Response.success(data={"updated": updated})


@router.put("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification_service.mark_notification_read(db, current_user, notification_id)
    return Response.success()
