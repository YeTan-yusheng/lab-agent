from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session


from app.schemas.reservation import (
    ReservationCreateRequest,
    AuditReservationRequest,
    CancelReservationRequest,
    AvailabilityRequest,
    DayAvailabilityRequest,
)
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
    lab_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = reservation_service.get_reservation_page_list(
        db,
        current_user,
        page,
        page_size,
        status,
        lab_id,
        date_from,
        date_to,
    )
    return Response.success(data=res)


@router.post("")
def create_reservation(
    payload: ReservationCreateRequest,
    request: Request,
    current_user: User = Depends(require_booking_capability),
    db: Session = Depends(get_db),
):
    reservation_service.create_reservation(
        db,
        current_user,
        payload,
        request_id=request.state.request_id,
    )
    return Response.success()


@router.post("/availability")
def check_availability(
    payload: AvailabilityRequest,
    current_user: User = Depends(require_booking_capability),
    db: Session = Depends(get_db),
):
    res = reservation_service.check_availability(db, payload)
    return Response.success(data=res)


@router.post("/availability/day")
def get_day_availability(
    payload: DayAvailabilityRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = reservation_service.get_day_availability(db, current_user, payload)
    return Response.success(data=res)


@router.get("/audit/pending-count")
def get_audit_pending_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = reservation_service.get_audit_pending_count(db, current_user)
    return Response.success(data={"count": count})


@router.get("/{reservation_id}/history")
def get_reservation_history(
    reservation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    history = reservation_service.get_reservation_history(
        db, current_user, reservation_id
    )
    return Response.success(
        data=[item.model_dump(mode="json") for item in history]
    )


@router.put("/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: int,
    request: Request,
    payload: CancelReservationRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = payload or CancelReservationRequest()
    reservation_service.cancel_reservation(
        db,
        reservation_id,
        current_user,
        reason=data.reason,
        force=data.force,
        request_id=request.state.request_id,
    )
    return Response.success()


@router.put("/{reservation_id}/audit")
def audit_reservation(
    reservation_id: int,
    payload: AuditReservationRequest,
    request: Request,
    current_user: User = Depends(require_capability(Capability.audit_reservation)),
    db: Session = Depends(get_db),
):
    reservation_service.audit_reservation(
        db,
        current_user,
        reservation_id,
        payload.status,
        reject_reason=payload.reject_reason,
        self_audit=payload.self_audit,
        request_id=request.state.request_id,
    )
    return Response.success()
