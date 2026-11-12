"""Core package: soft state engine + FitnessAgent."""

from .agent import FitnessAgent
from .state import get_system_snapshot

__all__ = ["FitnessAgent", "get_system_snapshot"]
