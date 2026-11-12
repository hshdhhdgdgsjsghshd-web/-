"""Key-free smoke test for three-table architecture + soft state."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import storage
from tools.log_manager import get_logs_by_date, log_meal, log_workout
from tools.plan_manager import get_active_plan, save_or_update_plan
from tools.profile_manager import get_user_profile, update_user_profile
from core.state import (
    STAGE_DAILY_COACHING,
    STAGE_ONBOARDING,
    STAGE_PLANNING,
    get_system_snapshot,
)


def _rebind(data_dir: Path) -> None:
    storage.DATA_DIR = data_dir
    import tools.log_manager as log_manager
    import tools.plan_manager as plan_manager
    import tools.profile_manager as profile_manager

    profile_manager.PROFILE_PATH = data_dir / "user_profile.json"
    profile_manager.PLAN_PATH = data_dir / "active_plan.json"
    plan_manager.PLAN_PATH = data_dir / "active_plan.json"
    log_manager.LOGS_PATH = data_dir / "daily_logs.json"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        _rebind(data_dir)
        storage.ensure_data_dir()

        snap = get_system_snapshot()
        assert snap["stage"] == STAGE_ONBOARDING
        assert "basic_metrics.gender" in snap["onboarding"]["missing_required_fields"]

        updated = update_user_profile(
            gender="男",
            age=28,
            height_cm=175,
            weight_kg=70,
            goal="减脂",
            cardio_level="有氧老手",
            strength_level="力量新手",
            available_equipment=["哑铃", "跑步机"],
            weekly_days=4,
            session_duration_min=60,
            append_injury="左膝偶尔不适",
        )
        assert updated["ok"]
        assert updated["is_onboarding_complete"] is True
        assert updated["baselines_recalculated"] is True
        baselines = updated["profile"]["calculated_baselines"]
        assert baselines["bmr"] > 0
        assert baselines["tdee"] > baselines["bmr"]
        assert 1.6 <= (baselines["target_protein_g"] / 70) <= 2.0

        snap = get_system_snapshot()
        assert snap["stage"] == STAGE_PLANNING

        plan = save_or_update_plan(
            reason="首次建档",
            replace_all=True,
            weekly_schedule={
                "Monday": {
                    "focus": "下肢力量",
                    "exercises": [{"name": "腿举", "sets": 3, "reps": 12}],
                    "status": "planned",
                },
                "Wednesday": {
                    "focus": "上肢推",
                    "exercises": ["哑铃卧推", "肩推"],
                    "status": "planned",
                },
                "Friday": {
                    "focus": "有氧恢复",
                    "exercises": ["跑步机 30min"],
                    "status": "planned",
                },
            },
        )
        assert plan["plan_version"] == 1
        assert get_active_plan()["is_empty"] is False

        snap = get_system_snapshot()
        assert snap["stage"] == STAGE_DAILY_COACHING

        # Cascade: weight change with active plan => action_required
        cascaded = update_user_profile(weight_kg=68)
        assert cascaded["action_required"] is not None
        assert cascaded["action_required"]["type"] == "ask_plan_resync"

        workout = log_workout(
            exercise="腿举",
            sets=3,
            reps=12,
            weight_kg=80,
            notes="RPE7，膝无痛",
        )
        assert workout["entry"]["volume_kg"] == 3 * 12 * 80
        meal = log_meal(
            meal_time="lunch",
            description="鸡胸肉沙拉",
            calories=450,
            protein_g=40,
            carbs_g=20,
            fat_g=18,
            is_estimated=True,
        )
        assert meal["ok"]
        today = get_logs_by_date()
        assert today["daily_summary"]["total_volume_kg"] == 2880
        assert today["daily_summary"]["total_calories"] == 450
        assert today["daily_summary"]["total_protein_g"] == 40

        # Partial plan update bumps version
        plan2 = save_or_update_plan(
            reason="膝盖替代：深蹲改腿举",
            weekly_schedule={
                "Monday": {
                    "focus": "下肢力量（膝友好）",
                    "exercises": [{"name": "腿举", "sets": 4, "reps": 10}],
                    "status": "adjusted",
                }
            },
        )
        assert plan2["plan_version"] == 2

        from tools import ALL_TOOLS

        assert len(ALL_TOOLS) == 7

        print(
            json.dumps(
                {
                    "stages_ok": True,
                    "baselines": baselines,
                    "action_required": cascaded["action_required"]["type"],
                    "today": today["daily_summary"],
                    "plan_version": plan2["plan_version"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print("smoke_tools: OK")


if __name__ == "__main__":
    main()
