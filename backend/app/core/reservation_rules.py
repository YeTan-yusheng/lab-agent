from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

# 占用资源的状态：0 待审核、1 已通过；2 已拒绝、3 已取消不占用
OCCUPYING_STATUSES: frozenset[int] = frozenset({0, 1})


@dataclass(frozen=True)
class RuleResult:
    allowed: bool
    reason_code: str
    message: str
    http_status: int = 200

    @classmethod
    def success(cls):
        return cls(allowed=True, reason_code="OK", message="请求成功")

    @classmethod
    def error(cls, reason_code: str, message: str, http_status: int):
        return cls(
            allowed=False,
            reason_code=reason_code,
            message=message,
            http_status=http_status,
        )


@dataclass(frozen=True)
class ConflictScope:
    """
    冲突范围
    作用：如果某个实验室被预约了，就不能预约这个实验室里的任何设备
        如果某个实验室里的某个设备被预约了，就不能预约整个实验室
        如果同一个实验室的不同设备被预约、不同实验室被预约、不同实验室的不同设备被预约，不会冲突

    any_reservation: True 表示同实验室任意预约都冲突； False 表示只与实验室预约和指定设备预约冲突
    """
    any_reservation: bool 
    equipment_id: int | None = None


def validate_time(date_str: str, start: str, end: str, now: datetime) -> RuleResult:
    """校验时间"""
    try:
        reservation_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        start_time = datetime.strptime(start, "%H:%M").time()
        end_time = datetime.strptime(end, "%H:%M").time()
    except (TypeError, ValueError):
        return RuleResult.error("INVALID_DATE_TIME", "预约日期或时间格式错误", 422)
    if end_time <= start_time:
        return RuleResult.error(
            "END_NOT_AFTER_START", "预约的结束时间必须晚于开始时间", 422
        )
    if reservation_date < now.date():
        return RuleResult.error("DATE_IN_PAST", "预约日期不能早于当前日期", 422)
    if reservation_date == now.date() and start_time < now.time():
        return RuleResult.error("START_IN_PAST", "预约开始时间不能早于当前时间", 422)
    return RuleResult.success()


def _iso_date(value: date | str) -> str:
    """将日期转为YYYY-MM-DD格式的字符串"""
    return value.isoformat() if isinstance(value, date) else value


def validate_lab(
    lab: Any,
    reservation_date: str,
    start: str,
    end: str,
    closed_days: Iterable[date | str],
) -> RuleResult:
    """校验实验室"""
    if lab is None:
        return RuleResult.error("LAB_NOT_FOUND", "实验室不存在", 404)
    if lab.status != 1:
        return RuleResult.error("LAB_CLOSED", "实验室已关闭", 409)
    if reservation_date in {_iso_date(item) for item in closed_days}:
        return RuleResult.error("LAB_CLOSED_DAY", "实验室闭馆日，无法预约", 409)
    if lab.open_time and start < lab.open_time:
        return RuleResult.error(
            "BEFORE_OPENING_TIME", "预约时间不能早于实验室的开放时间", 422
        )
    if lab.close_time and end > lab.close_time:
        return RuleResult.error(
            "AFTER_CLOSING_TIME", "预约时间不能晚于实验室的关闭时间", 422
        )
    return RuleResult.success()


def validate_equipment(equipment: Any, lab_id: int) -> RuleResult:
    """校验实验室设备"""
    if equipment is None:
        return RuleResult.error("EQUIPMENT_NOT_FOUND", "实验室设备不存在", 404)
    if equipment.lab_id != lab_id:
        return RuleResult.error("EQUIPMENT_NOT_IN_LAB", "实验室设备不属于该实验室", 400)
    if equipment.status != 1:
        return RuleResult.error("EQUIPMENT_UNDER_REPAIR", "实验室设备正在维修", 409)
    return RuleResult.success()


def conflict_scope(equipment_id: int | None) -> ConflictScope:
    """确定冲突范围"""
    if equipment_id is None:
        return ConflictScope(any_reservation=True)
    return ConflictScope(any_reservation=False, equipment_id=equipment_id)


def evaluate_conflicts(
    existing_equipment_ids: Iterable[int | None],
    requested_equipment_id: int | None,
) -> RuleResult:
    """
    评估预约冲突
    existing_equipment_ids: 过滤后的候选预约列表
    requested_equipment_id: 想要预约的设备
    """
    existing = set(existing_equipment_ids) # 去重
    if requested_equipment_id is None:
        if existing:
            return RuleResult.error("LAB_TIME_CONFLICT", "该时间段实验室已被预约", 409)
        return RuleResult.success()
    if None in existing:
        return RuleResult.error("LAB_TIME_CONFLICT", "该时间段实验室已被预约", 409)
    if requested_equipment_id in existing:
        return RuleResult.error(
            "EQUIPMENT_TIME_CONFLICT", "该时间段实验室设备已被预约", 409
        )
    return RuleResult.success()
