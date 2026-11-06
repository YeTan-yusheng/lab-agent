from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session


from app.schemas.reservation import ReservationCreateRequest, AuditReservationRequest
from app.models.user import User
from app.dependencies.auth import (
    get_current_user,
    require_booking_capability,
    require_capability,
)
from app.core.database import get_db
from app.services import reservation_service
from app.core.response import Response
from app.core.permissions import Capability

router = APIRouter(prefix="/reservation", tags=["预约相关接口"])


@router.get("/list")
def get_reservation_page_list(
    page: int = 1,
    page_size: int = 10,
    status: int | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = reservation_service.get_reservation_page_list(
        db, current_user, page, page_size, status
    )
    return Response.success(data=res)


@router.post("")
def create_reservation(
    payload: ReservationCreateRequest,
    current_user: User = Depends(require_booking_capability),
    db: Session = Depends(get_db),
):
    reservation_service.create_reservation(db, current_user, payload)
    return Response.success()


@router.put("/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation_service.cancel_reservation(db, reservation_id, current_user)
    return Response.success()


@router.put("/{reservation_id}/audit")
def audit_reservation(
    reservation_id: int,
    payload: AuditReservationRequest,
    current_user: User = Depends(require_capability(Capability.audit_reservation)),
    db: Session = Depends(get_db),
):
    reservation_service.audit_reservation(
        db, current_user, reservation_id, payload.status
    )
    return Response.success()
