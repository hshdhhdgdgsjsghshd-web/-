"""Active weekly plan manager — versioned schedule + OpenAI tool schemas."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .storage import (
    DATA_DIR,
    DEFAULT_ACTIVE_PLAN,
    WEEKDAYS,
    empty_day_plan,
    ensure_data_dir,
    read_json,
    utc_now_iso,
    write_json,
)

PLAN_PATH = DATA_DIR / "active_plan.json"

PLAN_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_active_plan",
            "description": "获取当前生效周计划（含 plan_version、weekly_schedule、adjustment_history）。",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_or_update_plan",
            "description": (
                "首次写入完整周计划，或局部修改某天/某几天计划。"
                "自动递增 plan_version，并把变更原因写入 adjustment_history。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "本次调整原因，如 首次建档 / 膝盖疼痛替代深蹲 / 热量基线变化",
                    },
                    "weekly_schedule": {
                        "type": "object",
                        "description": (
                            "可选：完整或部分周计划。键为 Monday~Sunday。"
                            "每天可含 focus、exercises、status。"
                        ),
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "focus": {"type": "string"},
                                "exercises": {
                                    "type": "array",
                                    "items": {
                                        "anyOf": [
                                            {"type": "string"},
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "sets": {"type": "integer"},
                                                    "reps": {"type": "integer"},
                                                    "notes": {"type": "string"},
                                                },
                                            },
                                        ]
                                    },
                                },
                                "status": {
                                    "type": "string",
                                    "enum": [
                                        "planned",
                                        "done",
                                        "skipped",
                                        "adjusted",
                                    ],
                                },
                            },
                        },
                    },
                    "replace_all": {
                        "type": "boolean",
                        "description": "true=用提供的 weekly_schedule 覆盖整周；false=仅合并给出的天数",
                        "default": False,
                    },
                },
                "required": ["reason"],
                "additionalProperties": False,
            },
        },
    },
]


def get_active_plan() -> dict[str, Any]:
    ensure_data_dir()
    plan = _normalize_plan(read_json(PLAN_PATH, DEFAULT_ACTIVE_PLAN))
    return {
        "ok": True,
        "plan": plan,
        "is_empty": not _plan_has_content(plan),
        "summary": summarize_plan(plan),
    }


def save_or_update_plan(
    reason: str,
    weekly_schedule: dict[str, Any] | None = None,
    replace_all: bool = False,
) -> dict[str, Any]:
    ensure_data_dir()
    plan = _normalize_plan(read_json(PLAN_PATH, DEFAULT_ACTIVE_PLAN))
    changed_days: list[str] = []

    if weekly_schedule:
        normalized_patch = _normalize_schedule_patch(weekly_schedule)
        if replace_all:
            new_schedule = {day: empty_day_plan() for day in WEEKDAYS}
            for day, payload in normalized_patch.items():
                new_schedule[day] = payload
                changed_days.append(day)
            plan["weekly_schedule"] = new_schedule
        else:
            for day, payload in normalized_patch.items():
                current = plan["weekly_schedule"].get(day) or empty_day_plan()
                merged = deepcopy(current)
                if "focus" in payload:
                    merged["focus"] = payload["focus"]
                if "exercises" in payload:
                    merged["exercises"] = payload["exercises"]
                if "status" in payload:
                    merged["status"] = payload["status"]
                plan["weekly_schedule"][day] = merged
                changed_days.append(day)

    plan["plan_version"] = int(plan.get("plan_version") or 0) + 1
    plan["updated_at"] = utc_now_iso()
    plan["adjustment_history"].append(
        {
            "at": plan["updated_at"],
            "version": plan["plan_version"],
            "reason": reason.strip(),
            "changed_days": changed_days,
            "replace_all": bool(replace_all),
        }
    )

    write_json(PLAN_PATH, plan)
    return {
        "ok": True,
        "plan_version": plan["plan_version"],
        "changed_days": changed_days,
        "plan": plan,
        "summary": summarize_plan(plan),
    }


def summarize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    schedule = plan.get("weekly_schedule") or {}
    days = []
    for day in WEEKDAYS:
        item = schedule.get(day) or {}
        exercises = item.get("exercises") or []
        days.append(
            {
                "day": day,
                "focus": item.get("focus"),
                "exercise_count": len(exercises),
                "status": item.get("status") or "planned",
            }
        )
    return {
        "plan_version": plan.get("plan_version", 0),
        "updated_at": plan.get("updated_at"),
        "active_training_days": [
            d["day"] for d in days if d["focus"] or d["exercise_count"] > 0
        ],
        "days": days,
        "adjustment_count": len(plan.get("adjustment_history") or []),
    }


def _plan_has_content(plan: dict[str, Any]) -> bool:
    if int(plan.get("plan_version") or 0) <= 0:
        return False
    for day in (plan.get("weekly_schedule") or {}).values():
        if not isinstance(day, dict):
            continue
        if day.get("focus") or day.get("exercises"):
            return True
    return False


def _normalize_plan(raw: Any) -> dict[str, Any]:
    plan = deepcopy(DEFAULT_ACTIVE_PLAN)
    if not isinstance(raw, dict):
        return plan
    plan["plan_version"] = int(raw.get("plan_version") or 0)
    plan["updated_at"] = raw.get("updated_at")
    plan["adjustment_history"] = list(raw.get("adjustment_history") or [])

    schedule = raw.get("weekly_schedule") or {}
    normalized = {day: empty_day_plan() for day in WEEKDAYS}
    for day in WEEKDAYS:
        incoming = schedule.get(day) or {}
        if not isinstance(incoming, dict):
            continue
        normalized[day] = {
            "focus": incoming.get("focus"),
            "exercises": list(incoming.get("exercises") or []),
            "status": incoming.get("status") or "planned",
        }
    plan["weekly_schedule"] = normalized
    return plan


def _normalize_schedule_patch(patch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw_day, payload in patch.items():
        day = _normalize_weekday(raw_day)
        if day is None or not isinstance(payload, dict):
            continue
        day_plan: dict[str, Any] = {}
        if "focus" in payload:
            day_plan["focus"] = payload.get("focus")
        if "exercises" in payload:
            day_plan["exercises"] = list(payload.get("exercises") or [])
        if "status" in payload:
            day_plan["status"] = payload.get("status") or "planned"
        result[day] = day_plan
    return result


def _normalize_weekday(value: str) -> str | None:
    text = str(value).strip()
    mapping = {
        "monday": "Monday",
        "mon": "Monday",
        "周一": "Monday",
        "星期一": "Monday",
        "tuesday": "Tuesday",
        "tue": "Tuesday",
        "周二": "Tuesday",
        "星期二": "Tuesday",
        "wednesday": "Wednesday",
        "wed": "Wednesday",
        "周三": "Wednesday",
        "星期三": "Wednesday",
        "thursday": "Thursday",
        "thu": "Thursday",
        "周四": "Thursday",
        "星期四": "Thursday",
        "friday": "Friday",
        "fri": "Friday",
        "周五": "Friday",
        "星期五": "Friday",
        "saturday": "Saturday",
        "sat": "Saturday",
        "周六": "Saturday",
        "星期六": "Saturday",
        "sunday": "Sunday",
        "sun": "Sunday",
        "周日": "Sunday",
        "星期日": "Sunday",
        "星期天": "Sunday",
    }
    if text in WEEKDAYS:
        return text
    return mapping.get(text.lower())
