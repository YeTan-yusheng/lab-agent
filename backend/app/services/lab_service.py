from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select

from app.core.response import PageResponse
from app.models.lab import Lab
from app.schemas.lab import LabResponse, LabCreateRequest, LabUpdateRequest
from app.core.exceptions import BusinessException


def get_labs_page_list(
    db: Session, page: int, page_size: int, keywords: str | None = None
) -> PageResponse:
    """分页模糊查询用户列表"""
    stmt = select(Lab)
    if keywords:
        stmt = stmt.where(
            or_(Lab.name.ilike(f"%{keywords}%"), Lab.location.ilike(f"%{keywords}%"))
        )

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()

    items = db.execute(
        stmt.order_by(Lab.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars()

    return PageResponse(
        list=[LabResponse.model_validate(item) for item in items], total=total
    )


def create_lab(db: Session, payload: LabCreateRequest) -> LabResponse:
    """实验室管理-新增实验室"""
    existing = db.execute(
        select(Lab).where(Lab.name == payload.name)
    ).scalar_one_or_none()

    if existing:
        raise BusinessException(message="实验室已存在")

    lab = Lab(**payload.model_dump())
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def update_lab(db: Session, lab_id: int, payload: LabUpdateRequest) -> LabResponse:
    """实验室管理-更新实验室"""
    lab = db.execute(select(Lab).where(Lab.id == lab_id)).scalar_one_or_none()
    if not lab:
        raise BusinessException(message="实验室不存在")

    payload = payload.model_dump(exclude_none=True)

    for filed, value in payload.items():
        setattr(lab, filed, value)

    db.commit()
    db.refresh(lab)
    return LabResponse.model_validate(lab)


def delete_lab(db: Session, lab_id: int):
    """实验室管理-删除实验室"""
    lab = db.query(Lab).filter(Lab.id == lab_id).first()
    if not lab:
        raise BusinessException(message="实验室不存在")
    db.delete(lab)
    db.commit()
