"""Daily logs manager — deterministic volume/nutrition totals + tool schemas."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .profile_manager import get_user_profile
from .storage import (
    DATA_DIR,
    DEFAULT_DAILY_LOGS,
    empty_day_log,
    ensure_data_dir,
    read_json,
    today_iso,
    write_json,
)

LOGS_PATH = DATA_DIR / "daily_logs.json"

LOG_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "log_workout",
            "description": (
                "记录单次训练。Python 自动计算 volume_kg = sets * reps * weight_kg，"
                "并累加到当日 daily_summary.total_volume_kg。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "日期 YYYY-MM-DD；缺省为今天",
                    },
                    "exercise": {"type": "string", "description": "动作名称"},
                    "sets": {"type": "integer", "minimum": 0},
                    "reps": {"type": "integer", "minimum": 0},
                    "weight_kg": {"type": "number", "minimum": 0},
                    "notes": {
                        "type": "string",
                        "description": "主观感受、RPE、疼痛反馈等",
                    },
                },
                "required": ["exercise", "sets", "reps", "weight_kg"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_meal",
            "description": (
                "记录单顿饮食。自动累加当日 total_calories 与 total_protein_g。"
                "模型可先估算宏量营养素；is_estimated=true 表示估算值。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "日期 YYYY-MM-DD；缺省为今天",
                    },
                    "meal_time": {
                        "type": "string",
                        "description": "餐次，如 breakfast / lunch / dinner / snack 或具体时间",
                    },
                    "description": {
                        "type": "string",
                        "description": "食物描述",
                    },
                    "calories": {"type": "number", "minimum": 0},
                    "protein_g": {"type": "number", "minimum": 0},
                    "carbs_g": {"type": "number", "minimum": 0},
                    "fat_g": {"type": "number", "minimum": 0},
                    "is_estimated": {
                        "type": "boolean",
                        "description": "是否为模型估算",
                        "default": True,
                    },
                },
                "required": [
                    "meal_time",
                    "description",
                    "calories",
                    "protein_g",
                    "carbs_g",
                    "fat_g",
                ],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_logs_by_date",
            "description": "查询指定日期（默认今日）完整流水，并对照档案目标给出完成度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {
                        "type": "string",
                        "description": "日期 YYYY-MM-DD；缺省为今天",
                    }
                },
                "additionalProperties": False,
            },
        },
    },
]


def log_workout(
    exercise: str,
    sets: int,
    reps: int,
    weight_kg: float,
    notes: str | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    ensure_data_dir()
    date_key = (date or today_iso()).strip()
    logs = _load_logs()
    day = _get_or_create_day(logs, date_key)

    volume_kg = float(sets) * float(reps) * float(weight_kg)
    entry = {
        "exercise": exercise.strip(),
        "sets": int(sets),
        "reps": int(reps),
        "weight_kg": float(weight_kg),
        "volume_kg": round(volume_kg, 2),
        "notes": (notes or "").strip(),
    }
    day["workouts"].append(entry)
    _recompute_summary(day)
    write_json(LOGS_PATH, logs)
    return {
        "ok": True,
        "date": date_key,
        "entry": entry,
        "daily_summary": day["daily_summary"],
    }


def log_meal(
    meal_time: str,
    description: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    is_estimated: bool = True,
    date: str | None = None,
) -> dict[str, Any]:
    ensure_data_dir()
    date_key = (date or today_iso()).strip()
    logs = _load_logs()
    day = _get_or_create_day(logs, date_key)

    entry = {
        "meal_time": meal_time.strip(),
        "description": description.strip(),
        "calories": float(calories),
        "protein_g": float(protein_g),
        "carbs_g": float(carbs_g),
        "fat_g": float(fat_g),
        "is_estimated": bool(is_estimated),
    }
    day["meals"].append(entry)
    _recompute_summary(day)
    write_json(LOGS_PATH, logs)
    return {
        "ok": True,
        "date": date_key,
        "entry": entry,
        "daily_summary": day["daily_summary"],
    }


def get_logs_by_date(date_str: str | None = None) -> dict[str, Any]:
    ensure_data_dir()
    date_key = (date_str or today_iso()).strip()
    logs = _load_logs()
    day = deepcopy(logs.get(date_key) or empty_day_log())
    _recompute_summary(day)

    profile = get_user_profile()["profile"]
    baselines = profile.get("calculated_baselines") or {}
    summary = day["daily_summary"]
    calorie_target = baselines.get("target_calories")
    protein_target = baselines.get("target_protein_g")

    return {
        "ok": True,
        "date": date_key,
        "workouts": day["workouts"],
        "meals": day["meals"],
        "daily_summary": summary,
        "targets": {
            "target_calories": calorie_target,
            "target_protein_g": protein_target,
        },
        "progress": {
            "calories_ratio": _ratio(summary["total_calories"], calorie_target),
            "protein_ratio": _ratio(summary["total_protein_g"], protein_target),
            "total_volume_kg": summary["total_volume_kg"],
        },
    }


def _load_logs() -> dict[str, Any]:
    raw = read_json(LOGS_PATH, DEFAULT_DAILY_LOGS)
    if not isinstance(raw, dict):
        return {}
    return raw


def _get_or_create_day(logs: dict[str, Any], date_key: str) -> dict[str, Any]:
    day = logs.get(date_key)
    if not isinstance(day, dict):
        day = empty_day_log()
        logs[date_key] = day
        return day
    day.setdefault("workouts", [])
    day.setdefault("meals", [])
    day.setdefault("daily_summary", empty_day_log()["daily_summary"])
    return day


def _recompute_summary(day: dict[str, Any]) -> None:
    workouts = day.get("workouts") or []
    meals = day.get("meals") or []
    total_volume = 0.0
    for item in workouts:
        if "volume_kg" in item and item["volume_kg"] is not None:
            total_volume += float(item["volume_kg"])
        else:
            total_volume += (
                float(item.get("sets") or 0)
                * float(item.get("reps") or 0)
                * float(item.get("weight_kg") or 0)
            )
    total_calories = sum(float(item.get("calories") or 0) for item in meals)
    total_protein = sum(float(item.get("protein_g") or 0) for item in meals)
    day["daily_summary"] = {
        "total_calories": round(total_calories, 1),
        "total_protein_g": round(total_protein, 1),
        "total_volume_kg": round(total_volume, 2),
    }


def _ratio(current: float, target: Any) -> float | None:
    if target in (None, "", 0):
        return None
    try:
        target_f = float(target)
    except (TypeError, ValueError):
        return None
    if target_f <= 0:
        return None
    return round(float(current) / target_f, 3)
