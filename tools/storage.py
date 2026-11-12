"""Shared JSON persistence — three-table source of truth."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

DEFAULT_USER_PROFILE: dict[str, Any] = {
    "is_onboarding_complete": False,
    "basic_metrics": {
        "gender": None,
        "age": None,
        "height_cm": None,
        "weight_kg": None,
        "goal": None,
    },
    "fitness_background": {
        "cardio_level": None,
        "strength_level": None,
        "available_equipment": [],
        "weekly_days": None,
        "session_duration_min": None,
    },
    "health_and_constraints": {
        "injuries": [],
        "dietary_restrictions": [],
    },
    "calculated_baselines": {
        "bmr": None,
        "tdee": None,
        "target_calories": None,
        "target_protein_g": None,
    },
}


def empty_day_plan() -> dict[str, Any]:
    return {
        "focus": None,
        "exercises": [],
        "status": "planned",  # planned | done | skipped | adjusted
    }


def empty_day_log() -> dict[str, Any]:
    return {
        "workouts": [],
        "meals": [],
        "daily_summary": {
            "total_calories": 0.0,
            "total_protein_g": 0.0,
            "total_volume_kg": 0.0,
        },
    }


DEFAULT_ACTIVE_PLAN: dict[str, Any] = {
    "plan_version": 0,
    "updated_at": None,
    "weekly_schedule": {day: empty_day_plan() for day in WEEKDAYS},
    "adjustment_history": [],
}

# daily_logs.json is a date-keyed map: { "YYYY-MM-DD": day_log }
DEFAULT_DAILY_LOGS: dict[str, Any] = {}

_FILE_LOCK = threading.Lock()


def ensure_data_dir() -> None:
    """Create data/ and default empty JSON tables when missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_json_file(DATA_DIR / "user_profile.json", DEFAULT_USER_PROFILE)
    _ensure_json_file(DATA_DIR / "active_plan.json", DEFAULT_ACTIVE_PLAN)
    _ensure_json_file(DATA_DIR / "daily_logs.json", DEFAULT_DAILY_LOGS)


def _ensure_json_file(path: Path, default: Any) -> None:
    if path.exists():
        return
    path.write_text(
        json.dumps(default, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path, default: Any) -> Any:
    ensure_data_dir()
    with _FILE_LOCK:
        if not path.exists():
            return deepcopy(default)
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return deepcopy(default)
        return json.loads(raw)


def write_json(path: Path, payload: Any) -> None:
    ensure_data_dir()
    with _FILE_LOCK:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def today_iso() -> str:
    return date.today().isoformat()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
