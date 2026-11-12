"""Shared JSON persistence helpers for fitness-coach-agent."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

DEFAULT_USER_PROFILE: dict[str, Any] = {
    "basic_info": {
        "gender": None,
        "age": None,
        "height_cm": None,
        "weight_kg": None,
        "goal": None,
    },
    "experience_profile": {
        "cardio_level": None,
        "strength_level": None,
        "available_equipment": [],
        "cross_tags": [],
    },
    "injuries": [],
    "daily_targets": {
        "calories_kcal": None,
        "protein_g": None,
    },
}

_FILE_LOCK = threading.Lock()


def ensure_data_dir() -> None:
    """Create data/ and default empty JSON structures when missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_json_file(DATA_DIR / "user_profile.json", DEFAULT_USER_PROFILE)
    _ensure_json_file(DATA_DIR / "workout_logs.json", [])
    _ensure_json_file(DATA_DIR / "diet_logs.json", [])


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
    from datetime import date

    return date.today().isoformat()
