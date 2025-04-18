"""Data models for meal recommendation API.

This module contains Pydantic models that define the structure of request and
response data for the meal recommendation API.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, field_validator, Field


class MacroNutrients(BaseModel):
    """Macro nutrient requirements or estimates.

    Attributes:
        calories: Target calories in kcal
        protein: Target protein in grams
        carbs: Target carbohydrates in grams
        fat: Target fat in grams
    """

    calories: float
    protein: float
    carbs: float
    fat: float

    @field_validator("calories", "protein", "carbs", "fat")
    def validate_positive(cls, value: float) -> float:
        """Validate that nutrient values are positive."""
        if value < 0:
            raise ValueError("Nutrient values must be positive")
        return value


class MealSuggestionRequest(BaseModel):
    """Request model for meal suggestions.

    Attributes:
        location: Geographic location for restaurant search
        calories: Target calories in kcal
        protein: Target protein in grams
        carbs: Target carbohydrates in grams
        fat: Target fat in grams
    """

    location: str
    calories: float
    protein: float
    carbs: float
    fat: float

    @field_validator("location")
    def validate_location(cls, value: str) -> str:
        """Validate that location is not empty."""
        if not value.strip():
            raise ValueError("Location cannot be empty")
        return value.strip()

    @field_validator("calories", "protein", "carbs", "fat")
    def validate_positive(cls, value: float) -> float:
        """Validate that nutrient values are positive."""
        if value < 0:
            raise ValueError("Macro values must be positive")
        return value


class Restaurant(BaseModel):
    """Restaurant information.

    Attributes:
        name: Restaurant name
        location: Restaurant address or location description
    """

    name: str
    location: Optional[str] = None


class MealSuggestion(BaseModel):
    """Meal suggestion model.

    Attributes:
        name: Name of the suggested meal
        description: Brief description of the meal
        macros: Estimated macro nutrients
        restaurant: Source restaurant information
    """

    name: str
    description: str
    macros: MacroNutrients
    restaurant: Restaurant

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Grilled Chicken Salad",
                "description": "Fresh salad with grilled chicken breast, mixed greens, and light dressing",
                "macros": {"calories": 450, "protein": 35, "carbs": 30, "fat": 15},
                "restaurant": {
                    "name": "Healthy Bites",
                    "location": "123 Main St, Finchley",
                },
            }
        }
    }


class MealSuggestionResponse(BaseModel):
    """Response model for meal suggestions.

    Attributes:
        meals: List of meal suggestions
    """

    meals: List[MealSuggestion]


class LogMealRequest(BaseModel):
    """Request model for logging a meal.

    Attributes:
        name: Name of the meal
        protein: Protein amount in grams
        carbs: Carbohydrate amount in grams
        fat: Fat amount in grams
        calories: Total calories
        meal_time: Timestamp of when the meal was consumed
    """

    name: str = Field(..., description="Name of the meal")
    protein: float = Field(..., description="Protein amount in grams", gt=0)
    carbs: float = Field(..., description="Carbohydrate amount in grams", gt=0)
    fat: float = Field(..., description="Fat amount in grams", gt=0)
    calories: float = Field(..., description="Total calories", gt=0)
    meal_time: Optional[datetime] = Field(
        default_factory=datetime.now, description="Timestamp of meal consumption"
    )


class LoggedMeal(LogMealRequest):
    """Logged meal model with additional tracking information.

    Attributes:
        id: Unique identifier for the logged meal
        user_id: ID of the user who logged the meal
        created_at: Timestamp when the meal was logged
    """

    id: str
    user_id: str
    created_at: datetime


class DailyProgressResponse(BaseModel):
    """Response model for daily macro progress.

    Attributes:
        logged_macros: Macros logged for the day
        target_macros: User's daily macro targets
        progress_percentage: Percentage of macro targets achieved
    """

    logged_macros: MacroNutrients
    target_macros: MacroNutrients
    progress_percentage: Dict[str, float]
