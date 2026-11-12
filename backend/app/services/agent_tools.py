import json
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session
from langchain_core.tools import tool
from datetime import datetime

from app.models.user import User, UserRoles
from app.services import kb_service, lab_service, equipment_service, reservation_service
from app.schemas.reservation import ReservationCreateRequest
from app.core.exceptions import BusinessException
from app.core.permissions import (
    Capability,
    RoleProfile,
    RoleValidationError,
    get_role_profile,
    validate_roles,
)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    required_capability: Capability  # 使用该工具需要的能力
    requires_confirmation: bool = False  # 是否需要人工确认
    owner_only: bool = False  # 是否只能操作自己的数据


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec("search_lab_docs", Capability.use_ai),
    ToolSpec("list_open_labs", Capability.use_ai),
    ToolSpec("list_lab_equipments", Capability.use_ai),
    ToolSpec("get_today", Capability.use_ai),
    ToolSpec(
        "create_lab_reservation",
        Capability.book_lab,
        requires_confirmation=True,
    ),
    ToolSpec(
        "create_equipment_reservation",
        Capability.book_equipment,
        requires_confirmation=True,
    ),
)

TOOL_SPEC_BY_NAME = {spec.name: spec for spec in TOOL_SPECS}


def _permission_error(message: str) -> str:
    """返回一个标准的权限错误响应"""
    return json.dumps(
        {"ok": False, "code": 403, "error": message},
        ensure_ascii=False,
    )


def _fresh_profile(db: Session, user_id: int) -> tuple[User | None, RoleProfile | None]:
    """重读用户和角色权限，返回最新的用户和角色权限信息"""
    # 结束当前事务快照，尽量看到其他会话已提交的角色变更
    db.rollback()
    db.expire_all()

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None or user.status != 1:
        return None, None
    role_codes = db.scalars(
        select(UserRoles.role_code).where(UserRoles.user_id == user_id)
    ).all()

    try:
        profile = validate_roles(role_codes)
    except RoleValidationError:
        return None, None
    return user, profile


def _tool_access_error(
    db: Session,
    user_id: int,
    tool_name: str,
    *,
    owner_user_id: int | None = None,
) -> str | None:
    """检查用户是否有权限使用指定的工具"""
    spec = TOOL_SPEC_BY_NAME.get(tool_name)
    if spec is None:
        return _permission_error(f"未知的工具: {tool_name}")

    user, profile = _fresh_profile(db, user_id)
    if user is None:
        return _permission_error("用户不存在或已被禁用")
    if profile is None:
        return _permission_error("当前账号没有使用该工具权限")
    if spec.owner_only and user_id != owner_user_id:
        return _permission_error("只能操作本人的数据")
    if not profile.has(spec.required_capability):
        return _permission_error("没有操作权限")
    return None


def visible_specs(profile: RoleProfile) -> list[ToolSpec]:
    """根据角色权限过滤可用工具"""
    return [spec for spec in TOOL_SPECS if profile.has(spec.required_capability)]


def _build_all_tools(db: Session, current_user: User):
    """构建所有工具的实现，返回一个列表，后续会根据用户角色权限过滤"""

    @tool
    def search_lab_docs(query: str):
        """查询知识库库"""
        denied = _tool_access_error(db, current_user.id, "search_lab_docs")
        if denied:
            return denied

        try:
            return kb_service.search(query) or "没有找到相关资料"
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": "search_lab_docs\n" + str(e)},
                ensure_ascii=False,
            )

    @tool
    def list_open_labs(keywords: str = "") -> str:
        """查询开放实验室"""
        denied = _tool_access_error(db, current_user.id, "list_open_labs")
        if denied:
            return denied

        try:
            keywords = keywords.strip() or None
            page = lab_service.get_labs_page_list(
                db, page=1, page_size=10, keywords=keywords, status=1
            )

            rows = [
                {
                    "id": item.id,
                    "name": item.name,
                    "location": item.location,
                    "capacity": item.capacity,
                    "open_time": item.open_time,
                    "close_time": item.close_time,
                }
                for item in page.list
            ]
            return json.dumps({"total": page.total, "labs": rows}, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": "list_open_labs\n" + str(e)}, ensure_ascii=False
            )

    @tool
    def list_lab_equipments(lab_id: int, keywords: str = "") -> str:
        """查询实验室设备"""
        denied = _tool_access_error(db, current_user.id, "list_lab_equipments")
        if denied:
            return denied

        try:
            keywords = keywords.strip() or None
            page = equipment_service.get_equipment_page_list(
                db, page=1, page_size=10, lab_id=lab_id, keywords=keywords
            )

            rows = [
                {
                    "id": item.id,
                    "name": item.name,
                    "lab_id": item.lab_id,
                    "lab_name": item.lab_name,
                    "sepc": item.spec,
                    "quantity": item.quantity,
                    "status": item.status,
                }
                for item in page.list
            ]
            return json.dumps(
                {"total": page.total, "equipments": rows}, ensure_ascii=False
            )
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": "list_lab_equipments\n" + str(e)},
                ensure_ascii=False,
            )

    @tool
    def create_equipment_reservation(
        lab_id: int,
        equipment_id: int,
        date: str,
        start_time: str,
        end_time: str,
        remark: str | None = None,
    ):
        """创建设备预约"""
        denied = _tool_access_error(
            db,
            current_user.id,
            "create_equipment_reservation",
        )
        if denied:
            return denied

        return _create_reservation(
            lab_id=lab_id,
            equipment_id=equipment_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            remark=remark,
        )

    @tool
    def create_lab_reservation(
        lab_id: int,
        date: str,
        start_time: str,
        end_time: str,
        remark: str | None = None,
    ):
        """创建实验室预约"""
        denied = _tool_access_error(
            db,
            current_user.id,
            "create_lab_reservation",
        )
        if denied:
            return denied

        return _create_reservation(
            lab_id=lab_id,
            equipment_id=None,
            date=date,
            start_time=start_time,
            end_time=end_time,
            remark=remark,
        )

    @tool
    def get_today() -> str:
        """获取当前时间 格式YYYY-MM-DD HH:MM:SS"""
        denied = _tool_access_error(db, current_user.id, "get_today")
        if denied:
            return denied
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _create_reservation(
        lab_id: int,
        equipment_id: int | None,
        date: str,
        start_time: str,
        end_time: str,
        remark: str | None = None,
    ):
        """创建预约记录"""
        payload = ReservationCreateRequest(
            lab_id=lab_id,
            equipment_id=equipment_id,
            date=date,
            start_time=start_time,
            end_time=end_time,
            remark=remark,
        )
        try:
            reservation_service.create_reservation(db, current_user, payload)
            return json.dumps(
                {"ok": True, "message": "预约提交成功，等待管理员审核"},
                ensure_ascii=False,
            )
        except BusinessException as e:
            return json.dumps(
                {"ok": False, "code": e.code, "error": e.message}, ensure_ascii=False
            )

    return [
        search_lab_docs,
        list_open_labs,
        list_lab_equipments,
        create_lab_reservation,
        create_equipment_reservation,
        get_today,
    ]


def build_tools(db: Session, current_user: User, profile: RoleProfile | None = None):
    """根据用户角色权限构建可用工具列表"""
    profile = profile or get_role_profile(current_user)
    all_tools = _build_all_tools(db, current_user)
    visible_names = {spec.name for spec in visible_specs(profile)}
    return [tool for tool in all_tools if tool.name in visible_names]
