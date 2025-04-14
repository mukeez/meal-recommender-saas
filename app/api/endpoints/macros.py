"""Macro calculation endpoints for the meal recommendation API.

This module contains the FastAPI routes for calculating macronutrient requirements
with support for both metric and imperial unit systems.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from enum import Enum
from typing import Dict, Optional

router = APIRouter()


class Sex(str, Enum):
    """Sex enumeration for BMR calculation."""
    MALE = "male"
    FEMALE = "female"


class ActivityLevel(str, Enum):
    """Activity level enumeration for TDEE calculation."""
    SEDENTARY = "sedentary"
    MODERATE = "moderate"
    ACTIVE = "active"


class Goal(str, Enum):
    """Fitness goal enumeration."""
    LOSE = "lose"
    MAINTAIN = "maintain"
    GAIN = "gain"


class UnitSystem(str, Enum):
    """Unit system enumeration for height and weight."""
    METRIC = "metric"
    IMPERIAL = "imperial"


class ManualMacros(BaseModel):
    """Manual macros input for overriding calculated values.

    Attributes:
        calories: User-specified daily calorie target
        protein: User-specified daily protein target in grams
        carbs: User-specified daily carbohydrate target in grams
        fat: User-specified daily fat target in grams
    """
    calories: int = Field(..., gt=0, description="Daily calorie target")
    protein: int = Field(..., ge=0, description="Daily protein target in grams")
    carbs: int = Field(..., ge=0, description="Daily carbohydrate target in grams")
    fat: int = Field(..., ge=0, description="Daily fat target in grams")


class MacroCalculatorRequest(BaseModel):
    """Request model for macro calculation.

    Attributes:
        age: User's age in years (18-100)
        weight: User's weight (in kg or lbs depending on unit_system)
        height: User's height (in cm or inches depending on unit_system)
        sex: User's biological sex (male/female)
        activity_level: User's activity level
        goal: User's fitness goal
        unit_system: Measurement system for weight and height
        manual_macros: Optional manual macros to override calculations
    """
    age: int = Field(..., ge=18, le=100, description="Age in years (18-100)")
    weight: float = Field(..., gt=0, description="Weight (in kg or lbs)")
    height: float = Field(..., gt=0, description="Height (in cm or inches)")
    sex: Sex = Field(..., description="Biological sex (male/female)")
    activity_level: ActivityLevel = Field(..., description="Activity level")
    goal: Goal = Field(..., description="Fitness goal")
    unit_system: UnitSystem = Field(..., description="Unit system for measurements")
    manual_macros: Optional[ManualMacros] = Field(None, description="Optional manual macro values")


class MacroCalculatorResponse(BaseModel):
    """Response model for macro calculation.

    Attributes:
        calories: Total daily calorie target
        protein: Daily protein target in grams
        carbs: Daily carbohydrate target in grams
        fat: Daily fat target in grams
    """
    calories: int = Field(..., description="Total daily calorie target")
    protein: int = Field(..., description="Daily protein target in grams")
    carbs: int = Field(..., description="Daily carbohydrate target in grams")
    fat: int = Field(..., description="Daily fat target in grams")


ACTIVITY_MULTIPLIERS: Dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725
}

GOAL_ADJUSTMENTS: Dict[Goal, float] = {
    Goal.LOSE: 0.8,
    Goal.MAINTAIN: 1.0,
    Goal.GAIN: 1.15
}

# Macronutrient constants
PROTEIN_PER_KG = 1.8
FAT_PER_KG = 1.0
PROTEIN_CALS_PER_GRAM = 4
FAT_CALS_PER_GRAM = 9
CARB_CALS_PER_GRAM = 4
MIN_CARBS_GRAMS = 50

LBS_TO_KG = 0.453592
INCHES_TO_CM = 2.54


def convert_to_metric(weight: float, height: float, unit_system: UnitSystem) -> tuple[float, float]:
    """Convert weight and height to metric units (kg and cm) if needed.

    Args:
        weight: Weight in original units
        height: Height in original units
        unit_system: Current unit system

    Returns:
        Tuple of (weight in kg, height in cm)
    """
    if unit_system == UnitSystem.IMPERIAL:
        weight_kg = weight * LBS_TO_KG
        height_cm = height * INCHES_TO_CM
        return weight_kg, height_cm
    else:
        return weight, height


def calculate_bmr(sex: Sex, weight_kg: float, height_cm: float, age: int) -> float:
    """Calculate Basal Metabolic Rate using the Mifflin-St Jeor Formula.

    Args:
        sex: User's biological sex
        weight_kg: Weight in kg
        height_cm: Height in cm
        age: Age in years

    Returns:
        BMR in calories per day
    """
    if sex == Sex.MALE:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


def calculate_tdee(bmr: float, activity_level: ActivityLevel) -> float:
    """Calculate Total Daily Energy Expenditure.

    Args:
        bmr: Basal Metabolic Rate
        activity_level: User's activity level

    Returns:
        TDEE in calories per day
    """
    return bmr * ACTIVITY_MULTIPLIERS[activity_level]


def adjust_for_goal(tdee: float, goal: Goal) -> int:
    """Adjust calories based on user's goal.

    Args:
        tdee: Total Daily Energy Expenditure
        goal: User's fitness goal

    Returns:
        Adjusted daily calories (rounded to integer)
    """
    return int(tdee * GOAL_ADJUSTMENTS[goal])


def calculate_macros(weight_kg: float, calories: int) -> MacroCalculatorResponse:
    """Calculate macronutrient distribution.

    Args:
        weight_kg: User's weight in kg
        calories: Total daily calories

    Returns:
        Calculated macronutrient targets
    """
    protein_g = int(weight_kg * PROTEIN_PER_KG)
    protein_cals = protein_g * PROTEIN_CALS_PER_GRAM

    fat_g = int(weight_kg * FAT_PER_KG)
    fat_cals = fat_g * FAT_CALS_PER_GRAM

    carbs_cals = calories - protein_cals - fat_cals
    carbs_g = int(carbs_cals / CARB_CALS_PER_GRAM)

    if carbs_g < MIN_CARBS_GRAMS:
        carbs_g = MIN_CARBS_GRAMS
        carbs_cals = carbs_g * CARB_CALS_PER_GRAM

        calories = protein_cals + fat_cals + carbs_cals

    return MacroCalculatorResponse(
        calories=calories,
        protein=protein_g,
        carbs=carbs_g,
        fat=fat_g
    )


@router.post(
    "/calculate-macros",
    response_model=MacroCalculatorResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate daily macronutrient targets",
    description="Calculate daily calorie and macronutrient targets based on personal metrics. Supports both metric and imperial units."
)
async def calculate_macros_endpoint(request: MacroCalculatorRequest) -> MacroCalculatorResponse:
    """Calculate daily macronutrient targets.

    This endpoint calculates Basal Metabolic Rate (BMR) using the Mifflin-St Jeor
    formula, then applies activity and goal adjustments to find Total Daily Energy
    Expenditure (TDEE). Macronutrients are then calculated based on protein and fat
    requirements, with remaining calories assigned to carbohydrates.

    Supports both metric and imperial units through unit_system parameter.

    Args:
        request: The calculation request with user metrics and goals

    Returns:
        The calculated macronutrient targets

    Raises:
        HTTPException: If there is an error processing the request
    """
    try:
        if request.manual_macros:
            return MacroCalculatorResponse(**request.manual_macros.dict())

        weight_kg, height_cm = convert_to_metric(
            request.weight,
            request.height,
            request.unit_system
        )

        bmr = calculate_bmr(
            request.sex,
            weight_kg,
            height_cm,
            request.age
        )

        tdee = calculate_tdee(bmr, request.activity_level)

        calories = adjust_for_goal(tdee, request.goal)

        return calculate_macros(weight_kg, calories)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating macros: {str(e)}"
        )