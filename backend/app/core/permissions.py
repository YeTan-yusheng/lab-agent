from collections.abc import Iterable
from enum import StrEnum
from dataclasses import dataclass

from app.models.user import User


class RoleValidationError(Exception):
    """角色校验异常"""

    def __init__(self, message: str, code: int = 422):
        self.message = message
        self.code = code
        super().__init__(message)


class Role(StrEnum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class Role_Name(StrEnum):
    student = "学生"
    teacher = "教师"
    admin = "管理员"


class Capability(StrEnum):
    book_equipment = "book_equipment"  # 预约设备
    book_lab = "book_lab"  # 预约实验室
    manage_resources = "manage_resources"  # 管理资源
    audit_reservation = "audit_reservation"  # 审核预约
    view_admin_stats = "view_admin_stats"  # 查看管理员统计
    manage_users = "manage_users"  # 管理用户
    manage_kb = "manage_kb"  # 管理知识库
    use_ai = "use_ai"  # 使用AI助手


# 角色能力映射
ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.student: frozenset([Capability.use_ai, Capability.book_equipment]),
    Role.teacher: frozenset(
        [Capability.book_equipment, Capability.book_lab, Capability.use_ai]
    ),
    Role.admin: frozenset(
        [
            Capability.manage_resources,
            Capability.audit_reservation,
            Capability.view_admin_stats,
            Capability.manage_users,
            Capability.manage_kb,
            Capability.use_ai,
        ]
    ),
}

# 允许的角色组合
ALLOWED_ROLE_COMBINATIONS = {
    frozenset({Role.student}),
    frozenset({Role.teacher}),
    frozenset({Role.admin}),
    frozenset({Role.teacher, Role.admin}),
}

# 排序顺序
ROLE_ORDER = (Role.student, Role.teacher, Role.admin)
CAPABILITY_ORDER = (
    Capability.book_equipment,
    Capability.book_lab,
    Capability.manage_resources,
    Capability.audit_reservation,
    Capability.view_admin_stats,
    Capability.manage_users,
    Capability.manage_kb,
    Capability.use_ai,
)


@dataclass(frozen=True)
class RoleProfile:
    roles: tuple[Role, ...]
    capabilities: frozenset[Capability]
    primary_role: Role
    display_name: str

    def __post_init__(self):
        if not self.roles:
            raise RoleValidationError(message="角色不能为空")
        if not isinstance(self.roles, tuple):
            raise RoleValidationError(message=f"错误的角色类型: {type(self.roles)}")
        for role in self.roles:
            if role not in Role.__members__:
                raise RoleValidationError(message=f"错误的角色: {role}")
        if frozenset(self.roles) not in ALLOWED_ROLE_COMBINATIONS:
            raise RoleValidationError(
                message=f"错误的角色组合: {frozenset(self.roles)}"
            )
        if not isinstance(self.capabilities, frozenset):
            raise RoleValidationError(
                message=f"错误的能力类型: {type(self.capabilities)}"
            )
        if self.capabilities != _capabilities_of(self.roles):
            raise RoleValidationError(
                message=f"错误的能力组合: {frozenset(self.capabilities)}"
            )
        for capability in self.capabilities:
            if capability not in Capability.__members__:
                raise RoleValidationError(message=f"错误的能力: {capability}")
        if self.primary_role not in self.roles:
            raise RoleValidationError(message=f"错误的主要角色: {self.primary_role}")
        if self.primary_role != (
            Role.admin
            if (Role.admin in self.roles)
            else (Role.teacher if (Role.teacher in self.roles) else Role.student)
        ):
            raise RoleValidationError(message=f"错误的主要角色: {self.primary_role}")
        if self.display_name != "/".join(
            role_name(r).value
            for r in sorted(self.roles, key=lambda r: ROLE_ORDER.index(r.value))
        ):
            raise RoleValidationError(message=f"错误的角色")
        if len(self.roles) != len(set(self.roles)):
            raise RoleValidationError(message="角色不能重复")

    def has(self, capability: Capability | str) -> bool:
        """检查是否具有指定能力"""
        if isinstance(capability, str) and capability in Capability.__members__:
            capability = Capability(capability)
        else:
            return False
        return capability in self.capabilities

    def to_api(self) -> dict:
        """把内部的 RoleProfile 转成稳定、可序列化的 API 数据，给登录、/me、用户列表和前端权限判断使用"""
        return {
            "roles": [
                role.value
                for role in sorted(self.roles, key=lambda r: ROLE_ORDER.index(r.value))
            ],
            "capabilities": [
                capability.value
                for capability in sorted(
                    self.capabilities, key=lambda c: CAPABILITY_ORDER.index(c.value)
                )
            ],
            "primary_role": self.primary_role.value,
            "display_name": self.display_name,
        }


def role_name(role: Role) -> Role_Name:
    """获取角色名称"""
    return Role_Name[role.value]


def normalize_roles(raw_roles: Iterable[Role | str]) -> tuple[Role, ...]:
    """把原始角色列表转换为标准化的角色元组"""
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    if not isinstance(raw_roles, Iterable):
        raise RoleValidationError(message="错误的类型")
    roles = []
    for role in raw_roles:
        if not isinstance(role, Role | str):
            raise RoleValidationError(message=f"错误的角色类型: {type(role)}")
        if isinstance(role, str):
            if role.strip().lower() not in Role.__members__:
                raise RoleValidationError(message=f"错误的角色: {role}")
            role = Role[role.strip().lower()]
        if role not in Role.__members__:
            raise RoleValidationError(message=f"错误的角色: {role}")
        roles.append(role)

    if not roles:
        raise RoleValidationError(message="角色不能为空")
    roles = list(dict.fromkeys(roles))
    return tuple(sorted(roles, key=lambda r: ROLE_ORDER.index(r.value)))


def is_allowed_combination(roles: Iterable[Role]) -> bool:
    """判断角色组合是否合法"""
    roles = frozenset(roles)
    if roles not in ALLOWED_ROLE_COMBINATIONS:
        return False
    return True


def _capabilities_of(roles: Iterable[Role]) -> frozenset[Capability]:
    """根据角色组合获取能力组合"""
    out: set[Capability] = set()
    for r in roles:
        out |= ROLE_CAPABILITIES.get(r, frozenset())
    return frozenset(out)


def validate_roles(raw_roles: Iterable[Role | str]) -> RoleProfile:
    """验证角色组合是否合法"""
    roles = normalize_roles(raw_roles)
    if not is_allowed_combination(roles):
        raise RoleValidationError(message=f"错误的角色组合: {frozenset(roles)}")

    # 合并角色能力
    capabilities = _capabilities_of(roles)

    if Role.admin in roles:
        primary_role = Role.admin
    elif Role.teacher in roles:
        primary_role = Role.teacher
    elif Role.student in roles:
        primary_role = Role.student
    display_name = "/".join([role_name(r).value for r in roles])

    return RoleProfile(
        roles=tuple(roles),
        capabilities=capabilities,
        primary_role=primary_role,
        display_name=display_name,
    )


def role_codes(roles: frozenset[Role]) -> list[str]:
    """根据角色组合获取角色代码列表"""
    if not roles:
        raise RoleValidationError(message="角色不能为空")
    return [
        role.value for role in sorted(roles, key=lambda r: ROLE_ORDER.index(r.value))
    ]


def capability_names(capabilities: frozenset[Capability]) -> list[str]:
    """根据能力组合获取能力名称列表"""
    if not capabilities:
        raise RoleValidationError(message="能力不能为空")
    return [
        capability.value
        for capability in sorted(
            capabilities, key=lambda c: CAPABILITY_ORDER.index(c.value)
        )
    ]


def booking_capability(equipment_id: int | None) -> Capability:
    return (
        Capability.book_equipment if equipment_id is not None else Capability.book_lab
    )


def get_role_profile(user: User) -> RoleProfile:
    role_codes = [item.role_code for item in user.roles]
    return validate_roles(role_codes)
