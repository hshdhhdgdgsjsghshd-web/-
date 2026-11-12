"""Fitness Coach deterministic tool package."""

from .log_manager import (
    LOG_TOOLS,
    get_logs_by_date,
    log_meal,
    log_workout,
)
from .plan_manager import (
    PLAN_TOOLS,
    get_active_plan,
    save_or_update_plan,
)
from .profile_manager import (
    PROFILE_TOOLS,
    get_user_profile,
    update_user_profile,
)

ALL_TOOLS = PROFILE_TOOLS + PLAN_TOOLS + LOG_TOOLS

TOOL_HANDLERS = {
    "get_user_profile": lambda **_: get_user_profile(),
    "update_user_profile": update_user_profile,
    "get_active_plan": lambda **_: get_active_plan(),
    "save_or_update_plan": save_or_update_plan,
    "log_workout": log_workout,
    "log_meal": log_meal,
    "get_logs_by_date": get_logs_by_date,
}

__all__ = [
    "ALL_TOOLS",
    "TOOL_HANDLERS",
    "PROFILE_TOOLS",
    "PLAN_TOOLS",
    "LOG_TOOLS",
    "get_user_profile",
    "update_user_profile",
    "get_active_plan",
    "save_or_update_plan",
    "log_workout",
    "log_meal",
    "get_logs_by_date",
]
