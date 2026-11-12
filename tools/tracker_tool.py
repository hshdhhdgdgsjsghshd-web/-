"""Workout & diet tracking tools — OpenAI function-calling schemas + executors."""

from __future__ import annotations

from typing import Any

from .storage import DATA_DIR, ensure_data_dir, read_json, today_iso, write_json
from .profile_tool import get_user_profile

WORKOUT_PATH = DATA_DIR / "workout_logs.json"
DIET_PATH = DATA_DIR / "diet_logs.json"

TRACKER_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "log_workout",
            "description": (
                "记录一条力量或有氧训练到 workout_logs.json。"
                "包含动作名、组数、次数、重量(kg)、主观感受/酸痛反馈(RPE)。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "训练日期 YYYY-MM-DD；缺省为今天",
                    },
                    "exercise": {
                        "type": "string",
                        "description": "动作或训练项目名称，如 深蹲、跑步 5km",
                    },
                    "sets": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "组数；有氧可填 1",
                    },
                    "reps": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "每组次数；有氧可用时长分钟数或配速相关次数占位",
                    },
                    "weight_kg": {
                        "type": "number",
                        "minimum": 0,
                        "description": "重量 kg；有氧可填 0",
                    },
                    "rpe_or_feeling": {
                        "type": "string",
                        "description": "主观感受 / 酸痛反馈，如 RPE7、膝盖轻微酸",
                    },
                },
                "required": ["exercise", "sets", "reps", "weight_kg", "rpe_or_feeling"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_diet",
            "description": (
                "记录一餐饮食到 diet_logs.json。"
                "模型应根据自然语言估算热量与三大营养素后再传入。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "日期 YYYY-MM-DD；缺省为今天",
                    },
                    "meal_name": {
                        "type": "string",
                        "description": "餐次或食物描述，如 午餐：鸡胸肉饭",
                    },
                    "calories": {
                        "type": "number",
                        "minimum": 0,
                        "description": "估算热量 kcal",
                    },
                    "protein_g": {
                        "type": "number",
                        "minimum": 0,
                        "description": "蛋白质 g",
                    },
                    "carbs_g": {
                        "type": "number",
                        "minimum": 0,
                        "description": "碳水 g",
                    },
                    "fat_g": {
                        "type": "number",
                        "minimum": 0,
                        "description": "脂肪 g",
                    },
                },
                "required": [
                    "meal_name",
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
            "name": "get_today_summary",
            "description": (
                "汇总今日已记录的训练条目，以及今日累计摄入的热量与蛋白质，"
                "并对照档案中的每日目标给出进度。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
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
    rpe_or_feeling: str,
    date: str | None = None,
) -> dict[str, Any]:
    """记录训练数据。"""
    ensure_data_dir()
    logs = read_json(WORKOUT_PATH, [])
    if not isinstance(logs, list):
        logs = []

    entry = {
        "date": (date or today_iso()).strip(),
        "exercise": exercise.strip(),
        "sets": int(sets),
        "reps": int(reps),
        "weight_kg": float(weight_kg),
        "rpe_or_feeling": rpe_or_feeling.strip(),
    }
    logs.append(entry)
    write_json(WORKOUT_PATH, logs)
    return {"ok": True, "entry": entry, "total_entries": len(logs)}


def log_diet(
    meal_name: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    date: str | None = None,
) -> dict[str, Any]:
    """记录饮食摄入。"""
    ensure_data_dir()
    logs = read_json(DIET_PATH, [])
    if not isinstance(logs, list):
        logs = []

    entry = {
        "date": (date or today_iso()).strip(),
        "meal_name": meal_name.strip(),
        "calories": float(calories),
        "protein_g": float(protein_g),
        "carbs_g": float(carbs_g),
        "fat_g": float(fat_g),
    }
    logs.append(entry)
    write_json(DIET_PATH, logs)
    return {"ok": True, "entry": entry, "total_entries": len(logs)}


def get_today_summary() -> dict[str, Any]:
    """汇总今日训练与饮食进度。"""
    ensure_data_dir()
    today = today_iso()
    workouts = [
        item
        for item in read_json(WORKOUT_PATH, [])
        if isinstance(item, dict) and item.get("date") == today
    ]
    diets = [
        item
        for item in read_json(DIET_PATH, [])
        if isinstance(item, dict) and item.get("date") == today
    ]

    calories = round(sum(float(item.get("calories") or 0) for item in diets), 1)
    protein = round(sum(float(item.get("protein_g") or 0) for item in diets), 1)
    carbs = round(sum(float(item.get("carbs_g") or 0) for item in diets), 1)
    fat = round(sum(float(item.get("fat_g") or 0) for item in diets), 1)

    profile = get_user_profile()["profile"]
    targets = profile.get("daily_targets") or {}
    calorie_target = targets.get("calories_kcal")
    protein_target = targets.get("protein_g")

    return {
        "ok": True,
        "date": today,
        "workouts": workouts,
        "workout_count": len(workouts),
        "diet": {
            "meals": diets,
            "meal_count": len(diets),
            "calories": calories,
            "protein_g": protein,
            "carbs_g": carbs,
            "fat_g": fat,
        },
        "targets": {
            "calories_kcal": calorie_target,
            "protein_g": protein_target,
        },
        "progress": {
            "calories_ratio": _ratio(calories, calorie_target),
            "protein_ratio": _ratio(protein, protein_target),
        },
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
    return round(current / target_f, 3)
