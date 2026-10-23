from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session


from app.schemas.reservation import ReservationCreateRequest
from app.models.user import User
from app.dependencies.auth import get_current_user
from app.core.database import get_db
from app.services import reservation_service
from app.core.response import Response

router = APIRouter(prefix="/reservation", tags=["预约相关接口"])


@router.post("")
def create_reservation(
    payload: ReservationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation_service.creaet_reservation(db, current_user, payload)
    return Response.success()
