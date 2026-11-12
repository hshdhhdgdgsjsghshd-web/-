"""Fitness Coach Agent tool package."""

from .profile_tool import (
    PROFILE_TOOLS,
    get_user_profile,
    update_user_profile,
)
from .tracker_tool import (
    TRACKER_TOOLS,
    get_today_summary,
    log_diet,
    log_workout,
)

ALL_TOOLS = PROFILE_TOOLS + TRACKER_TOOLS

TOOL_HANDLERS = {
    "get_user_profile": lambda **_: get_user_profile(),
    "update_user_profile": update_user_profile,
    "log_workout": log_workout,
    "log_diet": log_diet,
    "get_today_summary": lambda **_: get_today_summary(),
}

__all__ = [
    "ALL_TOOLS",
    "TOOL_HANDLERS",
    "PROFILE_TOOLS",
    "TRACKER_TOOLS",
    "get_user_profile",
    "update_user_profile",
    "log_workout",
    "log_diet",
    "get_today_summary",
]
