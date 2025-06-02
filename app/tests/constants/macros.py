from enum import Enum


class MacrosTestConstants(Enum):
    AGE = 30
    WEIGHT = 84
    HEIGHT = 1.8
    SEX = "male"
    ACTIVITY_LEVEL = "moderate"
    GOAL = "gain"
    UNIT_SYSTEM = "metric"
    MOCK_CALORIES = 2000
    MOCK_PROTEIN = 150
    MOCK_CARBS = 200
    MOCK_FAT = 70


# Convenient dictionary for test use
MOCK_MACRO_DATA = {
    "calories": MacrosTestConstants.MOCK_CALORIES.value,
    "protein": MacrosTestConstants.MOCK_PROTEIN.value,
    "carbs": MacrosTestConstants.MOCK_CARBS.value,
    "fat": MacrosTestConstants.MOCK_FAT.value
}

