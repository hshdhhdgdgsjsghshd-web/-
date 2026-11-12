"""Soft state engine — scan three tables and emit a system snapshot."""

from __future__ import annotations

from typing import Any

from tools.plan_manager import get_active_plan
from tools.profile_manager import get_user_profile, missing_required_fields
from tools.storage import today_iso
from tools.log_manager import get_logs_by_date

STAGE_ONBOARDING = "ONBOARDING"
STAGE_PLANNING = "PLANNING"
STAGE_DAILY_COACHING = "DAILY_COACHING"


def get_system_snapshot() -> dict[str, Any]:
    """Scan user_profile / active_plan / daily_logs and classify stage."""
    profile_result = get_user_profile()
    profile = profile_result["profile"]
    missing = missing_required_fields(profile)
    plan_result = get_active_plan()
    plan = plan_result["plan"]
    today_logs = get_logs_by_date(today_iso())

    if missing or not profile.get("is_onboarding_complete"):
        stage = STAGE_ONBOARDING
        priority = (
            "优先补齐档案必填项（性别、年龄、身高、体重、目标、有氧/力量基础）。"
            "可同时记录伤病或饮食限制，但先完成 onboarding。"
        )
    elif plan_result.get("is_empty", True):
        stage = STAGE_PLANNING
        priority = (
            "档案已齐，优先基于器械、每周天数与时长生成第一版周计划，"
            "并调用 save_or_update_plan 落盘。"
        )
    else:
        stage = STAGE_DAILY_COACHING
        priority = (
            "进入日常教练模式：对照今日计划督促执行，记录训练/饮食，"
            "并根据疼痛、进度或基线变化灵活修订计划。"
        )

    baselines = profile.get("calculated_baselines") or {}
    return {
        "stage": stage,
        "priority": priority,
        "date": today_iso(),
        "onboarding": {
            "is_complete": bool(profile.get("is_onboarding_complete")),
            "missing_required_fields": missing,
        },
        "profile_brief": {
            "goal": (profile.get("basic_metrics") or {}).get("goal"),
            "weight_kg": (profile.get("basic_metrics") or {}).get("weight_kg"),
            "cardio_level": (profile.get("fitness_background") or {}).get(
                "cardio_level"
            ),
            "strength_level": (profile.get("fitness_background") or {}).get(
                "strength_level"
            ),
            "injuries": (profile.get("health_and_constraints") or {}).get("injuries")
            or [],
            "target_calories": baselines.get("target_calories"),
            "target_protein_g": baselines.get("target_protein_g"),
        },
        "plan_brief": plan_result.get("summary"),
        "today_brief": {
            "daily_summary": today_logs.get("daily_summary"),
            "progress": today_logs.get("progress"),
            "workout_count": len(today_logs.get("workouts") or []),
            "meal_count": len(today_logs.get("meals") or []),
        },
        "policy": {
            "all_tools_always_open": True,
            "allow_cross_stage_updates": True,
            "note": (
                "状态仅用于优先级提示，不锁死工具。"
                "用户可随时改体重/伤病、修订计划或记录打卡。"
            ),
        },
    }


def format_snapshot_for_prompt(snapshot: dict[str, Any] | None = None) -> str:
    snap = snapshot or get_system_snapshot()
    missing = snap["onboarding"]["missing_required_fields"]
    missing_text = ", ".join(missing) if missing else "无"
    plan = snap.get("plan_brief") or {}
    today = snap.get("today_brief") or {}
    summary = today.get("daily_summary") or {}
    profile = snap.get("profile_brief") or {}

    return (
        "## 当前系统快照（由 get_system_snapshot 自动注入）\n"
        f"- 阶段: **{snap['stage']}**\n"
        f"- 日期: {snap['date']}\n"
        f"- 优先任务: {snap['priority']}\n"
        f"- Onboarding 完成: {snap['onboarding']['is_complete']}\n"
        f"- 缺失必填字段: {missing_text}\n"
        f"- 目标/体重: {profile.get('goal')} / {profile.get('weight_kg')}kg\n"
        f"- 经验: 有氧={profile.get('cardio_level')} · 力量={profile.get('strength_level')}\n"
        f"- 伤病: {profile.get('injuries') or '无'}\n"
        f"- 热量/蛋白质目标: {profile.get('target_calories')} kcal / "
        f"{profile.get('target_protein_g')} g\n"
        f"- 计划版本: v{plan.get('plan_version', 0)} · "
        f"训练日: {plan.get('active_training_days') or []}\n"
        f"- 今日: 热量 {summary.get('total_calories', 0)} · "
        f"蛋白质 {summary.get('total_protein_g', 0)}g · "
        f"容量 {summary.get('total_volume_kg', 0)}kg · "
        f"训练 {today.get('workout_count', 0)} 条 / 饮食 {today.get('meal_count', 0)} 条\n"
        "- 策略: 全工具始终开放；允许跨阶段修改档案、计划与日志。\n"
    )
