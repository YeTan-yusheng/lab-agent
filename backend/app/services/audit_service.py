from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.process_audit import ActionType, AgentToolCallingAudit, ProcessAudit


def add_success_audit(db: Session, **kwargs):
    """添加操作成功审计"""
    db.add(_build_audit_record(**kwargs))


def write_failed_audit(session_factory=None, **kwargs):
    """添加操作失败审计"""
    factory = session_factory or SessionLocal
    with factory() as session:
        session.add(_build_audit_record(**kwargs))
        session.commit()


def add_success_tool_calling_audit(db: Session, **kwargs):
    """添加工具调用成功审计"""
    db.add(_build_tool_calling_audit_record(**kwargs))


def write_failed_tool_calling_audit(session_factory=None, **kwargs):
    """添加工具调用失败审计"""
    factory = session_factory or SessionLocal
    with factory() as session:
        session.add(_build_tool_calling_audit_record(**kwargs))
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
        error_code=error_code[:64] if error_code is not None else None,
        user_agent=user_agent,
    )


def _build_tool_calling_audit_record(
    user_id: int,
    roles: str,
    capability: str,
    tool_name: str,
    request_id: str,
    result: str,
    error_code: str | None = None,
) -> AgentToolCallingAudit:
    return AgentToolCallingAudit(
        user_id=user_id,
        roles=roles,
        capability=capability,
        tool_name=tool_name,
        request_id=request_id,
        result=result,
        error_code=error_code[:64] if error_code is not None else None,
    )
