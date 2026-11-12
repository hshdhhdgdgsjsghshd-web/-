"""User profile tools — OpenAI function-calling schemas + executors."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .storage import (
    DATA_DIR,
    DEFAULT_USER_PROFILE,
    ensure_data_dir,
    read_json,
    write_json,
)

PROFILE_PATH = DATA_DIR / "user_profile.json"

PROFILE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": (
                "读取当前用户档案，包括基础身体数据、运动经验（含跨界标签）、"
                "伤病列表、每日热量与蛋白质目标。每次对话开始或给出训练/饮食建议前应调用。"
            ),
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
            "name": "update_user_profile",
            "description": (
                "当用户透露身体数据、运动背景（如跑步老手但力量新手）、可用器械或伤病史时，"
                "局部更新档案并保存。若同时提供身高/体重/年龄/性别，将用 Mifflin-St Jeor "
                "公式推算推荐热量与蛋白质目标。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gender": {
                        "type": "string",
                        "enum": ["男", "女", "male", "female", "other"],
                        "description": "性别",
                    },
                    "age": {"type": "integer", "minimum": 10, "maximum": 100},
                    "height_cm": {"type": "number", "minimum": 100, "maximum": 250},
                    "weight_kg": {"type": "number", "minimum": 30, "maximum": 300},
                    "goal": {
                        "type": "string",
                        "description": "训练目标，如减脂、增肌、体能提升、康复回归",
                    },
                    "cardio_level": {
                        "type": "string",
                        "description": "有氧基础，如 有氧新手 / 有氧中阶 / 有氧老手",
                    },
                    "strength_level": {
                        "type": "string",
                        "description": "力量基础，如 力量新手 / 力量中阶 / 力量老手",
                    },
                    "available_equipment": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "可用器械列表，如 杠铃、哑铃、跑步机、弹力带",
                    },
                    "cross_tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "跨界能力标签，如 有氧老手/力量新手",
                    },
                    "injuries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "伤病与疼痛部位列表；提到疼痛时必须更新",
                    },
                    "append_injury": {
                        "type": "string",
                        "description": "追加一条伤病/疼痛记录（不覆盖已有列表）",
                    },
                    "calories_kcal": {
                        "type": "integer",
                        "description": "手动覆盖每日热量目标（kcal）；通常由公式自动推算",
                    },
                    "protein_g": {
                        "type": "number",
                        "description": "手动覆盖每日蛋白质目标（g）；通常由公式自动推算",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
]


def get_user_profile() -> dict[str, Any]:
    """读取当前用户档案。"""
    ensure_data_dir()
    profile = read_json(PROFILE_PATH, DEFAULT_USER_PROFILE)
    return {"ok": True, "profile": _normalize_profile(profile)}


def update_user_profile(
    gender: str | None = None,
    age: int | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    goal: str | None = None,
    cardio_level: str | None = None,
    strength_level: str | None = None,
    available_equipment: list[str] | None = None,
    cross_tags: list[str] | None = None,
    injuries: list[str] | None = None,
    append_injury: str | None = None,
    calories_kcal: int | None = None,
    protein_g: float | None = None,
) -> dict[str, Any]:
    """局部更新用户档案；满足条件时自动推算每日目标。"""
    ensure_data_dir()
    profile = _normalize_profile(read_json(PROFILE_PATH, DEFAULT_USER_PROFILE))
    basic = profile["basic_info"]
    experience = profile["experience_profile"]
    targets = profile["daily_targets"]
    updated_fields: list[str] = []

    if gender is not None:
        basic["gender"] = _normalize_gender(gender)
        updated_fields.append("basic_info.gender")
    if age is not None:
        basic["age"] = int(age)
        updated_fields.append("basic_info.age")
    if height_cm is not None:
        basic["height_cm"] = float(height_cm)
        updated_fields.append("basic_info.height_cm")
    if weight_kg is not None:
        basic["weight_kg"] = float(weight_kg)
        updated_fields.append("basic_info.weight_kg")
    if goal is not None:
        basic["goal"] = goal.strip()
        updated_fields.append("basic_info.goal")

    if cardio_level is not None:
        experience["cardio_level"] = cardio_level.strip()
        updated_fields.append("experience_profile.cardio_level")
    if strength_level is not None:
        experience["strength_level"] = strength_level.strip()
        updated_fields.append("experience_profile.strength_level")
    if available_equipment is not None:
        experience["available_equipment"] = _dedupe_str_list(available_equipment)
        updated_fields.append("experience_profile.available_equipment")
    if cross_tags is not None:
        experience["cross_tags"] = _dedupe_str_list(cross_tags)
        updated_fields.append("experience_profile.cross_tags")

    # Auto-build crossover tags when both levels are known.
    experience["cross_tags"] = _ensure_cross_tags(
        experience.get("cardio_level"),
        experience.get("strength_level"),
        experience.get("cross_tags") or [],
    )

    if injuries is not None:
        profile["injuries"] = _dedupe_str_list(injuries)
        updated_fields.append("injuries")
    if append_injury:
        injury = append_injury.strip()
        if injury and injury not in profile["injuries"]:
            profile["injuries"].append(injury)
            updated_fields.append("injuries.append")

    auto_targets = None
    if _can_estimate_targets(basic):
        auto_targets = estimate_daily_targets(
            gender=basic["gender"],
            age=int(basic["age"]),
            height_cm=float(basic["height_cm"]),
            weight_kg=float(basic["weight_kg"]),
            goal=basic.get("goal"),
        )
        targets["calories_kcal"] = auto_targets["calories_kcal"]
        targets["protein_g"] = auto_targets["protein_g"]
        updated_fields.extend(
            ["daily_targets.calories_kcal", "daily_targets.protein_g"]
        )

    if calories_kcal is not None:
        targets["calories_kcal"] = int(calories_kcal)
        updated_fields.append("daily_targets.calories_kcal")
    if protein_g is not None:
        targets["protein_g"] = round(float(protein_g), 1)
        updated_fields.append("daily_targets.protein_g")

    write_json(PROFILE_PATH, profile)
    return {
        "ok": True,
        "updated_fields": sorted(set(updated_fields)),
        "auto_targets": auto_targets,
        "profile": profile,
        "injury_alert": bool(profile["injuries"]),
    }


def estimate_daily_targets(
    *,
    gender: str,
    age: int,
    height_cm: float,
    weight_kg: float,
    goal: str | None = None,
) -> dict[str, Any]:
    """Mifflin-St Jeor BMR → 推荐热量与蛋白质目标。"""
    bmr = mifflin_st_jeor(gender=gender, age=age, height_cm=height_cm, weight_kg=weight_kg)
    goal_text = (goal or "").lower()
    # Activity multiplier tuned by goal wording.
    if any(k in goal_text for k in ("减脂", "减重", "瘦", "lose", "cut")):
        multiplier = 1.35
        protein_per_kg = 2.0
    elif any(k in goal_text for k in ("增肌", "增重", "bulk", "gain", "肌肉")):
        multiplier = 1.65
        protein_per_kg = 1.8
    elif any(k in goal_text for k in ("康复", "恢复", "pain", "injury")):
        multiplier = 1.4
        protein_per_kg = 1.6
    else:
        multiplier = 1.55
        protein_per_kg = 1.6

    calories = int(round(bmr * multiplier / 10) * 10)
    protein = round(weight_kg * protein_per_kg, 1)
    return {
        "bmr_kcal": round(bmr, 1),
        "multiplier": multiplier,
        "calories_kcal": calories,
        "protein_g": protein,
        "formula": "Mifflin-St Jeor",
    }


def mifflin_st_jeor(
    *,
    gender: str,
    age: int,
    height_cm: float,
    weight_kg: float,
) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    normalized = _normalize_gender(gender)
    if normalized == "女":
        return base - 161
    # Default to male formula for 男 / other / unknown when estimating.
    return base + 5


def _normalize_profile(raw: Any) -> dict[str, Any]:
    profile = deepcopy(DEFAULT_USER_PROFILE)
    if not isinstance(raw, dict):
        return profile

    basic = raw.get("basic_info") or {}
    experience = raw.get("experience_profile") or {}
    targets = raw.get("daily_targets") or {}

    profile["basic_info"].update(
        {
            "gender": basic.get("gender"),
            "age": basic.get("age"),
            "height_cm": basic.get("height_cm"),
            "weight_kg": basic.get("weight_kg"),
            "goal": basic.get("goal"),
        }
    )
    profile["experience_profile"].update(
        {
            "cardio_level": experience.get("cardio_level"),
            "strength_level": experience.get("strength_level"),
            "available_equipment": _dedupe_str_list(
                experience.get("available_equipment") or []
            ),
            "cross_tags": _dedupe_str_list(experience.get("cross_tags") or []),
        }
    )
    profile["injuries"] = _dedupe_str_list(raw.get("injuries") or [])
    profile["daily_targets"].update(
        {
            "calories_kcal": targets.get("calories_kcal"),
            "protein_g": targets.get("protein_g"),
        }
    )
    return profile


def _normalize_gender(gender: str) -> str:
    value = gender.strip().lower()
    if value in {"女", "female", "f", "woman", "women"}:
        return "女"
    if value in {"男", "male", "m", "man", "men"}:
        return "男"
    return gender.strip()


def _can_estimate_targets(basic: dict[str, Any]) -> bool:
    return all(
        basic.get(key) not in (None, "")
        for key in ("gender", "age", "height_cm", "weight_kg")
    )


def _dedupe_str_list(items: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _ensure_cross_tags(
    cardio_level: str | None,
    strength_level: str | None,
    existing: list[str],
) -> list[str]:
    tags = list(existing)
    if cardio_level and strength_level:
        auto = f"{cardio_level}/{strength_level}"
        if auto not in tags:
            tags.append(auto)
    return _dedupe_str_list(tags)
