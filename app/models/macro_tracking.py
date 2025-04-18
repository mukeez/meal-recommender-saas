"""Data models for daily macro tracking.

This module contains Pydantic models for tracking daily macro nutrient intake.
"""

from datetime import datetime
from pydantic import BaseModel, Field


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
