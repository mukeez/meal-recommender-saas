"""Data models for daily macro tracking.

This module contains Pydantic models for tracking daily macro nutrient intake.
"""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import Optional
from app.models.user import Sex, HeightUnitPreference, WeightUnitPreference
from datetime import date




class ActivityLevel(str, Enum):
    """Activity level enumeration for TDEE calculation."""

    SEDENTARY = "sedentary"
    MODERATE = "moderate"
    ACTIVE = "active"


class GoalType(str, Enum):
    """Fitness goal enumeration."""

    LOSE = "lose"
    MAINTAIN = "maintain"
    GAIN = "gain"


class DailyMacroProgress(BaseModel):
    """Model representing a user's daily macro nutrient progress.

    Attributes:
        user_id: Unique identifier for the user
        date: Date of the progress record
        current_protein: Current protein intake in grams
        current_carbs: Current carbohydrate intake in grams
        current_fats: Current fat intake in grams
        protein_goal: Daily protein goal in grams
        carbs_goal: Daily carbohydrate goal in grams
        fats_goal: Daily fat goal in grams
    """

    user_id: str
    date: datetime = Field(default_factory=datetime.now)
    current_protein: float = Field(ge=0, default=0)
    current_carbs: float = Field(ge=0, default=0)
    current_fats: float = Field(ge=0, default=0)
    protein_goal: float = Field(ge=0)
    carbs_goal: float = Field(ge=0)
    fats_goal: float = Field(ge=0)

    def calculate_progress_percentage(self) -> float:
        """
        Calculate the overall macro progress percentage.

        Returns:
            float: Percentage of daily macro goals achieved (0-100)
        """
        progress_components = [
            (
                min(1.0, self.current_protein / self.protein_goal)
                if self.protein_goal > 0
                else 0
            ),
            (
                min(1.0, self.current_carbs / self.carbs_goal)
                if self.carbs_goal > 0
                else 0
            ),
            min(1.0, self.current_fats / self.fats_goal) if self.fats_goal > 0 else 0,
        ]

        return round(sum(progress_components) / len(progress_components) * 100, 2)




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
        weight: User's weight (in kg or lbs depending on weight_unit_preference)
        height: User's height (in cm or feet depending on height_unit_preference)
        sex: User's biological sex (male/female)
        activity_level: User's activity level
        dob: Optional date of birth in YYYY-MM-DD format
        dietary_preference: Optional dietary preferences (e.g., vegetarian, vegan)
        goal_type: User's fitness goal type (lose, maintain, gain)
        progress_rate: Target rate of weight change in weight units per week (negative for loss)
        target_weight: Optional target weight (used to calculate time to goal)
        height_unit_preference: Unit for height measurements (metric: cm, imperial: feet)
        weight_unit_preference: Unit for weight measurements (metric: kg, imperial: lbs)
        manual_macros: Optional manual macros to override calculations
    """
    age: int = Field(..., ge=18, le=100, description="Age in years (18-100)")
    weight: float = Field(..., gt=0, description="Weight (in kg or lbs)")
    height: float = Field(..., gt=0, description="Height (in cm or feet)")
    sex: Sex = Field(..., description="Biological sex (male/female)")
    dob: Optional[str] = Field(
        None,
        description="Date of birth in YYYY-MM-DD format (optional)")
    activity_level: ActivityLevel = Field(..., description="Activity level")
    goal_type: GoalType = Field(..., description="Type of fitness goal")
    dietary_preference: Optional[str] = Field(
        None, description="User's dietary preferences (e.g., vegetarian, vegan)"
    )
    progress_rate: float = Field(0, description="Target rate of weight change in weight units/week (negative for loss)")
    target_weight: Optional[float] = Field(None, gt=0, description="Target weight (optional)")
    height_unit_preference: HeightUnitPreference = Field(HeightUnitPreference.METRIC, description="Unit for height measurements (metric: cm, imperial: feet)")
    weight_unit_preference: WeightUnitPreference = Field(WeightUnitPreference.METRIC, description="Unit for weight measurements (metric: kg, imperial: lbs)")
    manual_macros: Optional[ManualMacros] = Field(
        None, description="Optional manual macro values"
    )


    @field_validator('dob')
    @classmethod
    def validate_dob(cls, v):
        """Validate that dob is a valid date string in ISO format (YYYY-MM-DD)."""
        if v is None:
            return v
            
        try:
            # Try to parse the string as a date
            date.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("Date of birth must be a valid date string in ISO format (YYYY-MM-DD)")


class TimeToGoal(BaseModel):
    """Time to reach weight goal."""
    weeks: float = Field(..., description="Estimated weeks to reach goal")
    days: int = Field(..., description="Estimated days to reach goal")
    estimated_date: Optional[str] = Field(None, description="Estimated completion date")
    is_possible: bool = Field(..., description="Whether the goal is possible")
    message: Optional[str] = Field(None, description="Additional information")


class MacroCalculatorResponse(BaseModel):
    """Response model for macro calculation.

    Attributes:
        calories: Daily calorie target in kcal
        protein: Daily protein target in grams
        carbs: Daily carbohydrate target in grams
        fat: Daily fat target in grams
        dietary_preference: User's dietary preferences (if provided)
        progress_rate: Actual weekly weight change rate
        deficit_surplus: Daily calorie deficit/surplus
        is_safe: Whether the calorie target is safe
        time_to_goal: Time estimation to reach target weight (if provided)
    """
    calories: int = Field(..., gt=0, description="Daily calorie target in kcal")
    protein: int = Field(..., ge=0, description="Daily protein target in grams")
    carbs: int = Field(..., ge=0, description="Daily carbohydrate target in grams")
    fat: int = Field(..., ge=0, description="Daily fat target in grams")
    target_weight: Optional[float] = Field(
        None, gt=0, description="Target weight in kg or lbs (if provided)"
    )
    goal_type: Optional[str] = Field(None, description="Type of fitness goal")
    dietary_preference: Optional[str] = Field(
        None, description="User's dietary preferences (e.g., vegetarian, vegan)"
    )
    progress_rate: Optional[float] = Field(None, description="Actual weekly weight change rate")
    deficit_surplus: Optional[int] = Field(None, description="Daily calorie deficit/surplus. If the user is maintaining weight, this will be 0 else it will be a positive or negative integer indicating the surplus or deficit respectively.")
    is_safe: Optional[bool] = Field(True, description="Whether the calorie target is safe")
    time_to_goal: Optional[TimeToGoal] = Field(None, description="Time estimation to reach goal")


class MacroDistributionRequest(BaseModel):
    """Request model for adjusting macro distribution.
    
    Attributes:
        protein: Target protein in grams (optional)
        carbs: Target carbs in grams (optional)
        fat: Target fat in grams (optional)
    """
    protein: Optional[int] = Field(None, ge=0, description="Target protein in grams")
    carbs: Optional[int] = Field(None, ge=0, description="Target carbs in grams")
    fat: Optional[int] = Field(None, ge=0, description="Target fat in grams")
    
    @field_validator('protein', 'carbs', 'fat')
    @classmethod
    def check_at_least_one_macro(cls, v, info):
        """Validate that at least one macro target is specified."""
        # Get the current field name
        current_field = info.field_name
        
        # If the current value is not None, no need to check further
        if v is not None:
            return v
            
        # Get all values so far
        values = info.data
        
        # Check if at least one of the other macro fields is not None
        other_fields = [f for f in ['protein', 'carbs', 'fat'] if f != current_field]
        if all(values.get(field) is None for field in other_fields if field in values):
            # If we're validating the last field and no other field has a value
            if current_field == 'fat' and all(values.get(field) is None for field in ['protein', 'carbs']):
                raise ValueError("At least one macro target (protein, carbs, or fat) must be specified")
                
        return v