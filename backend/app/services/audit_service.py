from sqlalchemy.orm import Session
from sqlalchemy import func, or_, select

from app.models.process_audit import ProcessAudit


from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.process_audit import ActionType, ProcessAudit
from app.core.response import PageResponse


def add_success_audit(db: Session, **kwargs):
    """添加操作成功审计"""
    db.add(_build_audit_record(**kwargs))


def write_failed_audit(session_factory=None, **kwargs):
    """添加操作失败审计"""
    factory = session_factory or SessionLocal
    with factory() as session:
        session.add(_build_audit_record(**kwargs))
        session.commit()


def _build_audit_record(
    actor_user_id: int,
    target_user_id: int,
    action: ActionType,
    result: str,
    request_id: str,
    old_roles: str | None = None,
    new_roles: str | None = None,
    ip: str | None = None,
    error_code: str | None = None,
    user_agent: str | None = None,
) -> ProcessAudit:
    return ProcessAudit(
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        action=action,
        result=result,
        request_id=request_id,
        old_roles=old_roles,
        new_roles=new_roles,
        ip=ip,
        error_code=error_code[:64],
        user_agent=user_agent,
    )
