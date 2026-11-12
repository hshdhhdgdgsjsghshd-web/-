"""User profile manager — deterministic baselines + OpenAI tool schemas."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .storage import (
    DATA_DIR,
    DEFAULT_ACTIVE_PLAN,
    DEFAULT_USER_PROFILE,
    ensure_data_dir,
    read_json,
    write_json,
)

PROFILE_PATH = DATA_DIR / "user_profile.json"
PLAN_PATH = DATA_DIR / "active_plan.json"

REQUIRED_ONBOARDING_FIELDS = (
    ("basic_metrics", "gender"),
    ("basic_metrics", "age"),
    ("basic_metrics", "height_cm"),
    ("basic_metrics", "weight_kg"),
    ("basic_metrics", "goal"),
    ("fitness_background", "cardio_level"),
    ("fitness_background", "strength_level"),
)

PROFILE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "读取当前用户静态/低频基础档案（含计算出的 BMR/TDEE/目标热量与蛋白质）。",
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
                "局部更新档案任意字段。自动校验 onboarding 必填项并重算 Mifflin-St Jeor "
                "BMR/TDEE/目标热量与蛋白质。若体重或目标变化且已有生效计划，返回 "
                "action_required 提示，要求主动询问是否同步修订计划。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gender": {"type": "string", "description": "性别：男/女"},
                    "age": {"type": "integer", "minimum": 10, "maximum": 100},
                    "height_cm": {"type": "number", "minimum": 100, "maximum": 250},
                    "weight_kg": {"type": "number", "minimum": 30, "maximum": 300},
                    "goal": {
                        "type": "string",
                        "description": "目标，如 减脂 / 增肌 / 维持 / 体能提升",
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
                        "description": "可用器械列表",
                    },
                    "weekly_days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 7,
                        "description": "每周可训练天数",
                    },
                    "session_duration_min": {
                        "type": "integer",
                        "minimum": 15,
                        "maximum": 180,
                        "description": "单次训练时长（分钟）",
                    },
                    "injuries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "伤病列表（覆盖写入）",
                    },
                    "append_injury": {
                        "type": "string",
                        "description": "追加一条伤病/疼痛记录",
                    },
                    "dietary_restrictions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "饮食限制（覆盖写入）",
                    },
                    "append_dietary_restriction": {
                        "type": "string",
                        "description": "追加一条饮食限制",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
]


def get_user_profile() -> dict[str, Any]:
    ensure_data_dir()
    profile = _normalize_profile(read_json(PROFILE_PATH, DEFAULT_USER_PROFILE))
    return {
        "ok": True,
        "profile": profile,
        "missing_required_fields": missing_required_fields(profile),
    }


def update_user_profile(
    gender: str | None = None,
    age: int | None = None,
    height_cm: float | None = None,
    weight_kg: float | None = None,
    goal: str | None = None,
    cardio_level: str | None = None,
    strength_level: str | None = None,
    available_equipment: list[str] | None = None,
    weekly_days: int | None = None,
    session_duration_min: int | None = None,
    injuries: list[str] | None = None,
    append_injury: str | None = None,
    dietary_restrictions: list[str] | None = None,
    append_dietary_restriction: str | None = None,
) -> dict[str, Any]:
    ensure_data_dir()
    profile = _normalize_profile(read_json(PROFILE_PATH, DEFAULT_USER_PROFILE))
    before_weight = profile["basic_metrics"].get("weight_kg")
    before_goal = profile["basic_metrics"].get("goal")
    updated_fields: list[str] = []

    basic = profile["basic_metrics"]
    fitness = profile["fitness_background"]
    health = profile["health_and_constraints"]

    if gender is not None:
        basic["gender"] = _normalize_gender(gender)
        updated_fields.append("basic_metrics.gender")
    if age is not None:
        basic["age"] = int(age)
        updated_fields.append("basic_metrics.age")
    if height_cm is not None:
        basic["height_cm"] = float(height_cm)
        updated_fields.append("basic_metrics.height_cm")
    if weight_kg is not None:
        basic["weight_kg"] = float(weight_kg)
        updated_fields.append("basic_metrics.weight_kg")
    if goal is not None:
        basic["goal"] = str(goal).strip()
        updated_fields.append("basic_metrics.goal")

    if cardio_level is not None:
        fitness["cardio_level"] = str(cardio_level).strip()
        updated_fields.append("fitness_background.cardio_level")
    if strength_level is not None:
        fitness["strength_level"] = str(strength_level).strip()
        updated_fields.append("fitness_background.strength_level")
    if available_equipment is not None:
        fitness["available_equipment"] = _dedupe_str_list(available_equipment)
        updated_fields.append("fitness_background.available_equipment")
    if weekly_days is not None:
        fitness["weekly_days"] = int(weekly_days)
        updated_fields.append("fitness_background.weekly_days")
    if session_duration_min is not None:
        fitness["session_duration_min"] = int(session_duration_min)
        updated_fields.append("fitness_background.session_duration_min")

    if injuries is not None:
        health["injuries"] = _dedupe_str_list(injuries)
        updated_fields.append("health_and_constraints.injuries")
    if append_injury:
        text = append_injury.strip()
        if text and text not in health["injuries"]:
            health["injuries"].append(text)
            updated_fields.append("health_and_constraints.injuries.append")
    if dietary_restrictions is not None:
        health["dietary_restrictions"] = _dedupe_str_list(dietary_restrictions)
        updated_fields.append("health_and_constraints.dietary_restrictions")
    if append_dietary_restriction:
        text = append_dietary_restriction.strip()
        if text and text not in health["dietary_restrictions"]:
            health["dietary_restrictions"].append(text)
            updated_fields.append("health_and_constraints.dietary_restrictions.append")

    missing = missing_required_fields(profile)
    profile["is_onboarding_complete"] = len(missing) == 0

    baselines_recalculated = False
    if _can_recalculate(basic):
        profile["calculated_baselines"] = calculate_baselines(
            gender=basic["gender"],
            age=int(basic["age"]),
            height_cm=float(basic["height_cm"]),
            weight_kg=float(basic["weight_kg"]),
            goal=basic.get("goal"),
            weekly_days=fitness.get("weekly_days"),
        )
        baselines_recalculated = True
        updated_fields.append("calculated_baselines")

    write_json(PROFILE_PATH, profile)

    weight_changed = weight_kg is not None and before_weight != basic.get("weight_kg")
    goal_changed = goal is not None and before_goal != basic.get("goal")
    plan_active = has_active_plan()
    action_required = None
    if plan_active and (weight_changed or goal_changed) and baselines_recalculated:
        action_required = {
            "type": "ask_plan_resync",
            "reason": "weight_or_goal_changed_with_active_plan",
            "message": (
                "热量基线已因体重/目标变化而重算。请主动提醒用户，并询问是否同步修订 "
                "active_plan 周计划（可用 save_or_update_plan）。"
            ),
            "changed": {
                "weight_kg": {"before": before_weight, "after": basic.get("weight_kg")}
                if weight_changed
                else None,
                "goal": {"before": before_goal, "after": basic.get("goal")}
                if goal_changed
                else None,
            },
            "new_baselines": profile["calculated_baselines"],
        }

    return {
        "ok": True,
        "updated_fields": sorted(set(updated_fields)),
        "is_onboarding_complete": profile["is_onboarding_complete"],
        "missing_required_fields": missing,
        "baselines_recalculated": baselines_recalculated,
        "action_required": action_required,
        "profile": profile,
    }


def calculate_baselines(
    *,
    gender: str,
    age: int,
    height_cm: float,
    weight_kg: float,
    goal: str | None = None,
    weekly_days: int | None = None,
) -> dict[str, Any]:
    """Deterministic Mifflin-St Jeor → BMR / TDEE / targets."""
    bmr = mifflin_st_jeor(
        gender=gender, age=age, height_cm=height_cm, weight_kg=weight_kg
    )
    activity = _activity_factor(weekly_days)
    tdee = bmr * activity
    goal_text = (goal or "").lower()

    if any(k in goal_text for k in ("减脂", "减重", "瘦", "cut", "lose")):
        target_calories = tdee * 0.8
        protein_per_kg = 1.8  # within 1.6–2.0 for fat loss
    elif any(k in goal_text for k in ("增肌", "增重", "bulk", "gain", "肌肉")):
        target_calories = tdee * 1.1
        protein_per_kg = 1.8
    elif any(k in goal_text for k in ("维持", "maintain")):
        target_calories = tdee
        protein_per_kg = 1.6
    else:
        target_calories = tdee
        protein_per_kg = 1.6

    return {
        "bmr": round(bmr, 1),
        "tdee": round(tdee, 1),
        "target_calories": int(round(target_calories / 10) * 10),
        "target_protein_g": round(weight_kg * protein_per_kg, 1),
        "activity_factor": activity,
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
    if _normalize_gender(gender) == "女":
        return base - 161
    return base + 5


def missing_required_fields(profile: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for section, key in REQUIRED_ONBOARDING_FIELDS:
        value = (profile.get(section) or {}).get(key)
        if value in (None, "", []):
            missing.append(f"{section}.{key}")
    return missing


def has_active_plan() -> bool:
    plan = read_json(PLAN_PATH, DEFAULT_ACTIVE_PLAN)
    if not isinstance(plan, dict):
        return False
    if int(plan.get("plan_version") or 0) <= 0:
        return False
    schedule = plan.get("weekly_schedule") or {}
    for day in schedule.values():
        if not isinstance(day, dict):
            continue
        if day.get("focus") or day.get("exercises"):
            return True
    return False


def _activity_factor(weekly_days: int | None) -> float:
    if weekly_days is None:
        return 1.55
    days = int(weekly_days)
    if days <= 1:
        return 1.2
    if days <= 3:
        return 1.375
    if days <= 5:
        return 1.55
    return 1.725


def _can_recalculate(basic: dict[str, Any]) -> bool:
    return all(
        basic.get(key) not in (None, "")
        for key in ("gender", "age", "height_cm", "weight_kg")
    )


def _normalize_profile(raw: Any) -> dict[str, Any]:
    profile = deepcopy(DEFAULT_USER_PROFILE)
    if not isinstance(raw, dict):
        return profile

    for section in (
        "basic_metrics",
        "fitness_background",
        "health_and_constraints",
        "calculated_baselines",
    ):
        incoming = raw.get(section) or {}
        if isinstance(incoming, dict):
            profile[section].update(incoming)

    profile["fitness_background"]["available_equipment"] = _dedupe_str_list(
        profile["fitness_background"].get("available_equipment") or []
    )
    profile["health_and_constraints"]["injuries"] = _dedupe_str_list(
        profile["health_and_constraints"].get("injuries") or []
    )
    profile["health_and_constraints"]["dietary_restrictions"] = _dedupe_str_list(
        profile["health_and_constraints"].get("dietary_restrictions") or []
    )
    profile["is_onboarding_complete"] = len(missing_required_fields(profile)) == 0
    return profile


def _normalize_gender(gender: str) -> str:
    value = gender.strip().lower()
    if value in {"女", "female", "f", "woman", "women"}:
        return "女"
    if value in {"男", "male", "m", "man", "men"}:
        return "男"
    return gender.strip()


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
