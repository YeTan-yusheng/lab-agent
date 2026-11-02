from dataclasses import FrozenInstanceError

import pytest

from app.core.permissions import (
    ROLE_CAPABILITIES,
    Capability,
    Role,
    RoleProfile,
    RoleValidationError,
    capability_names,
    is_allowed_combination,
    normalize_roles,
    role_codes,
    validate_roles,
)

ALL_CAPABILITIES = [
    "book_equipment",
    "book_lab",
    "manage_resources",
    "audit_reservation",
    "view_admin_stats",
    "manage_users",
    "manage_kb",
    "use_ai",
]

VALID_CASES = [
    (
        ["student"],
        ["student"],
        ["book_equipment", "use_ai"],
        "student",
        "学生",
    ),
    (
        ["teacher"],
        ["teacher"],
        ["book_equipment", "book_lab", "use_ai"],
        "teacher",
        "教师",
    ),
    (
        ["admin"],
        ["admin"],
        [
            "manage_resources",
            "audit_reservation",
            "view_admin_stats",
            "manage_users",
            "manage_kb",
            "use_ai",
        ],
        "admin",
        "管理员",
    ),
    (
        ["teacher", "admin"],
        ["teacher", "admin"],
        ALL_CAPABILITIES,
        "admin",
        "教师/管理员",
    ),
    (
        ["admin", "teacher"],
        ["teacher", "admin"],
        ALL_CAPABILITIES,
        "admin",
        "教师/管理员",
    ),
]


@pytest.mark.parametrize(
    "raw_roles, expected_roles, expected_capabilities, expected_primary, expected_display",
    VALID_CASES,
)
def test_validate_roles_contract(
    raw_roles,
    expected_roles,
    expected_capabilities,
    expected_primary,
    expected_display,
):
    """测试角色组合验证"""
    profile = validate_roles(raw_roles)

    assert profile.roles == tuple(Role(role) for role in expected_roles)
    assert profile.primary_role == Role(expected_primary)
    assert profile.display_name == expected_display
    assert profile.to_api() == {
        "roles": expected_roles,
        "capabilities": expected_capabilities,
        "primary_role": expected_primary,
        "display_name": expected_display,
    }


@pytest.mark.parametrize(
    "raw_roles, expected_roles, expected_capabilities, expected_primary, expected_display",
    VALID_CASES,
)
def test_validate_roles_has(
    raw_roles,
    expected_roles,
    expected_capabilities,
    expected_primary,
    expected_display,
):
    """测试角色能力验证"""
    profile = validate_roles(raw_roles)
    expected = set(expected_capabilities)

    for capability in ALL_CAPABILITIES:
        assert profile.has(capability) == (capability in expected)

    assert profile.has(Capability.book_lab) == ("book_lab" in expected)
    assert profile.has("not_a_capability") is False


@pytest.mark.parametrize(
    "raw_roles",
    [
        [],
        ["admin", "student"],
        ["student", "teacher"],
        ["admin", "student", "teacher"],
        ["unknown"],
    ],
)
def test_validate_roles_rejects_invalid_combinations(raw_roles):
    """测试角色组合验证"""
    with pytest.raises(RoleValidationError):
        validate_roles(raw_roles)


def test_validate_roles_deduplicates_roles():
    """测试角色去重"""
    profile = validate_roles(["teacher", "teacher"])
    assert profile.roles == (Role.teacher,)
    assert profile.display_name == "教师"


@pytest.mark.parametrize(
    "raw_roles, expected",
    [
        (["student"], (Role.student,)),
        ([" TEACHER ", "teacher"], (Role.teacher,)),
        ([Role.admin, Role.teacher], (Role.teacher, Role.admin)),
        (["admin", "teacher"], (Role.teacher, Role.admin)),
    ],
)
def test_normalize_roles(raw_roles, expected):
    """测试角色转换"""
    assert normalize_roles(raw_roles) == expected


def test_normalize_single_string():
    """测试单个字符串转换"""
    assert normalize_roles("student") == (Role.student,)


def test_normalize_empty_generator():
    """测试空生成器转换"""
    with pytest.raises(RoleValidationError):
        normalize_roles(iter(()))


@pytest.mark.parametrize("raw_roles", [None, 123, [None], [123]])
def test_normalize_rejects_bad_types(raw_roles):
    """测试角色转换异常"""
    with pytest.raises(RoleValidationError):
        normalize_roles(raw_roles)


@pytest.mark.parametrize(
    "roles",
    [
        ("student",),
        ("teacher",),
        ("admin",),
        ("teacher", "admin"),
        ("admin", "teacher"),
    ],
)
def test_is_allowed_combination_accepts(roles):
    """测试角色组合验证"""
    assert is_allowed_combination(roles) is True


@pytest.mark.parametrize(
    "roles",
    [
        (),
        ("admin", "student"),
        ("student", "teacher"),
        ("admin", "student", "teacher"),
        ("unknown",),
    ],
)
def test_is_allowed_combination_rejects(roles):
    """测试角色组合验证异常"""
    assert is_allowed_combination(roles) is False


def test_role_codes_order():
    """测试角色代码排序"""
    assert role_codes(frozenset({Role.admin, Role.teacher})) == ["teacher", "admin"]


def test_capability_names_order():
    """测试能力排序"""
    assert capability_names(ROLE_CAPABILITIES[Role.teacher]) == [
        "book_equipment",
        "book_lab",
        "use_ai",
    ]


def test_profile_is_frozen():
    """测试角色配置冻结"""
    profile = validate_roles(["student"])
    with pytest.raises(FrozenInstanceError):
        profile.display_name = "另一个名字"


def test_profile_rejects_inconsistent_capabilities():
    """测试角色私有能力验证"""
    with pytest.raises(RoleValidationError):
        RoleProfile(
            roles=(Role.student,),
            capabilities=frozenset(),
            primary_role=Role.student,
            display_name="学生",
        )
