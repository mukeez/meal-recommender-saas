from enum import Enum
from app.models.macro_tracking import Sex, ActivityLevel, GoalType, UnitPreference


class MacrosTestConstants(Enum):
    """Constants for testing the macros endpoints."""
    AGE = 30
    WEIGHT = 80.0  # kg
    HEIGHT = 180.0  # cm
    SEX = Sex.MALE.value
    ACTIVITY_LEVEL = ActivityLevel.MODERATE.value
    GOAL_TYPE = GoalType.MAINTAIN.value
    PROGRESS_RATE = 0.0  # No weight change
    UNIT_PREFERENCE = UnitPreference.METRIC.value


# Mock data for macro calculator response
MOCK_MACRO_DATA = {
    "calories": 2000,
    "protein": 150,
    "carbs": 200,
    "fat": 67,
    "progress_rate": 0.0,
    "deficit_surplus": 0,
    "is_safe": True
}

# Mock data for time to goal calculation
MOCK_TIME_TO_GOAL = {
    "weeks": 10.0,
    "days": 70,
    "estimated_date": "2025-06-20",
    "is_possible": True
}

