"""Key-free smoke test for Sprint 1 tools."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import storage
from tools.profile_tool import get_user_profile, mifflin_st_jeor, update_user_profile
from tools.tracker_tool import get_today_summary, log_diet, log_workout


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        storage.DATA_DIR = data_dir
        # Rebind module-level paths used by tools.
        import tools.profile_tool as profile_tool
        import tools.tracker_tool as tracker_tool

        profile_tool.PROFILE_PATH = data_dir / "user_profile.json"
        tracker_tool.WORKOUT_PATH = data_dir / "workout_logs.json"
        tracker_tool.DIET_PATH = data_dir / "diet_logs.json"

        storage.ensure_data_dir()
        assert (data_dir / "user_profile.json").exists()

        bmr = mifflin_st_jeor(gender="男", age=30, height_cm=175, weight_kg=70)
        assert 1600 < bmr < 1800, bmr

        updated = update_user_profile(
            gender="男",
            age=30,
            height_cm=175,
            weight_kg=70,
            goal="增肌",
            cardio_level="有氧老手",
            strength_level="力量新手",
            available_equipment=["哑铃", "跑步机"],
            append_injury="左膝偶尔疼痛",
        )
        assert updated["ok"]
        assert updated["auto_targets"]["calories_kcal"] > 0
        assert "有氧老手/力量新手" in updated["profile"]["experience_profile"]["cross_tags"]
        assert "左膝偶尔疼痛" in updated["profile"]["injuries"]

        log_workout(
            exercise="哑铃肩推",
            sets=3,
            reps=10,
            weight_kg=12,
            rpe_or_feeling="RPE7，肩部可控",
        )
        log_diet(
            meal_name="午餐：鸡胸肉糙米饭",
            calories=620,
            protein_g=45,
            carbs_g=70,
            fat_g=15,
        )
        summary = get_today_summary()
        assert summary["workout_count"] == 1
        assert summary["diet"]["calories"] == 620
        profile = get_user_profile()["profile"]
        assert profile["daily_targets"]["protein_g"] is not None

        print(
            json.dumps(
                {
                    "bmr": round(bmr, 1),
                    "auto_targets": updated["auto_targets"],
                    "summary": {
                        "workouts": summary["workout_count"],
                        "calories": summary["diet"]["calories"],
                        "protein_g": summary["diet"]["protein_g"],
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print("smoke_tools: OK")


if __name__ == "__main__":
    main()
