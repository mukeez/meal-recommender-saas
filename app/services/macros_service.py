from typing import Dict, Any, Optional, Tuple, Union
import logging
from datetime import datetime, timedelta
import math

from app.models.macro_tracking import (
    Sex,
    ActivityLevel,
    GoalType,
    UnitPreference,
    MacroCalculatorResponse,
)
from app.services.base_database_service import BaseDatabaseService
from app.utils.constants import INCHES_TO_CM, LBS_TO_KG, CALORIES_PER_KG, PROTEIN_PER_KG, FAT_PER_KG, PROTEIN_CALS_PER_GRAM, FAT_CALS_PER_GRAM, CARB_CALS_PER_GRAM, MIN_CARBS_GRAMS

logger = logging.getLogger(__name__)



MIN_SAFE_CALORIES = {Sex.MALE: 1500, Sex.FEMALE: 1200}
MAX_SAFE_DEFICIT = 1000
MAX_SAFE_SURPLUS = 800

# Activity level multipliers for TDEE calculation
ACTIVITY_MULTIPLIERS: Dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.MODERATE: 1.55,
    ActivityLevel.ACTIVE: 1.725,
}

class MacrosServiceError(Exception):
    """Custom exception for macros service errors."""

    pass


class MacrosService:
    """
    Service for calculating and managing macronutrient targets and preferences.

    This service contains methods for calculating BMR, TDEE, and macronutrient
    targets based on user metrics, as well as methods for saving and retrieving
    user preferences from the database.
    """


    def __init__(self):
        """
        Initialize the MacrosService and check for available database implementation.

        Raises:
            MacrosServiceError: If no database service implementation is available.
        """
        if not BaseDatabaseService.subclasses:
            raise MacrosServiceError("No database service implementation available")

    def convert_to_metric(
        self, weight: float, height: float,  target_weight: float, unit_preference: UnitPreference, progress_rate: Optional[float] = None
    ) -> Tuple[float, float, float]:
        """
        Convert weight, height, and optionally progress rate to metric units (kg and cm) if needed.

        Args:
            weight: Weight in original units
            height: Height in original units
            target_weight: Target weight in original units
            unit_preference: Current unit system
            progress_rate: Weekly weight change rate in original units (optional)

        Returns:
            Tuple of (weight in kg, height in cm, target_weight in kg, progress_rate in kg/week)
        """
        if unit_preference == UnitPreference.IMPERIAL:
            weight_kg = weight * LBS_TO_KG
            height_cm = height * INCHES_TO_CM
            target_weight_kg = target_weight * LBS_TO_KG
            progress_rate_kg = progress_rate * LBS_TO_KG

            return weight_kg, height_cm, target_weight_kg, progress_rate_kg
                
        else:   
            return weight, height, target_weight, progress_rate

    def calculate_bmr(
        self, sex: Sex, weight_kg: float, height_cm: float, age: int
    ) -> float:
        """
        Calculate Basal Metabolic Rate using the Mifflin-St Jeor Formula.

        Args:
            sex: User's biological sex
            weight_kg: Weight in kg
            height_cm: Height in cm
            age: Age in years

        Returns:
            BMR in calories per day
        """
        if sex == Sex.MALE:
            return (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
        else:
            return (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

    def calculate_tdee(self, bmr: float, activity_level: ActivityLevel) -> float:
        """
        Calculate Total Daily Energy Expenditure.

        Args:
            bmr: Basal Metabolic Rate
            activity_level: User's activity level

        Returns:
            TDEE in calories per day
        """
        return bmr * ACTIVITY_MULTIPLIERS[activity_level]

    def adjust_for_goal(
        self,
        tdee: float,
        goal_type: GoalType,
        progress_rate: float,
        sex: Sex
    ) -> Dict[str, Any]:
        """
        Adjust calories based on user's weight change goal.

        Args:
            tdee: Total Daily Energy Expenditure
            goal_type: Type of goal (lose, maintain, gain)
            progress_rate: Target rate of weight change in kg/week
            sex: User's biological sex (for minimum calorie safety check)

        Returns:
            Dictionary with adjusted calories and safety information
        """
        if goal_type == GoalType.MAINTAIN or progress_rate == 0:
            return {
                "calories": int(tdee),
                "deficit_surplus": 0,
                "progress_rate": 0,
                "is_safe": True,
            }
        
        daily_adjustment = (progress_rate * CALORIES_PER_KG) / 7

        # Apply adjustment to TDEE
        adjusted_calories = int(tdee + daily_adjustment)

        is_safe = True
        min_calories = MIN_SAFE_CALORIES[sex]

        # Check if below minimum safe calories
        if adjusted_calories < min_calories:
            is_safe = False

        # Define safety thresholds in kg/week
        max_safe_deficit_kg = MAX_SAFE_DEFICIT / (CALORIES_PER_KG / 7)
        max_safe_surplus_kg = MAX_SAFE_SURPLUS / (CALORIES_PER_KG / 7)

        # Check if deficit or surplus exceeds safe limits (in kg/week)
        if goal_type == GoalType.LOSE and abs(progress_rate) > max_safe_deficit_kg:
            is_safe = False
        elif goal_type == GoalType.GAIN and abs(progress_rate) > max_safe_surplus_kg:
            is_safe = False

        return {
            "calories": adjusted_calories,
            "deficit_surplus": int(daily_adjustment),
            "progress_rate": progress_rate,
            "is_safe": is_safe,
        }

    def calculate_macros(
        self, weight_kg: float, calories: int
    ) -> MacroCalculatorResponse:
        """
        Calculate macronutrient distribution.

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
            calories=calories, protein=protein_g, carbs=carbs_g, fat=fat_g
        )

    def calculate_time_to_goal(
        self, current_weight: float, target_weight: float, progress_rate: float, 
    ) -> Dict[str, Any]:
        """
        Calculate time needed to reach target weight at given rate.

        Args:
            current_weight: Current weight
            target_weight: Target weight
            progress_rate: Weekly weight

        Returns:
            Dictionary with weeks, days and estimated date
        """
        if progress_rate == 0:
            return {
                "weeks": float("inf"),
                "days": float("inf"),
                "estimated_date": None,
                "is_possible": False,
            }

        # Check if goal direction matches rate direction
        weight_diff = target_weight - current_weight
        if (weight_diff < 0 and progress_rate > 0) or (
            weight_diff > 0 and progress_rate < 0
        ):
            return {
                "weeks": 0,
                "days": 0,
                "estimated_date": None,
                "is_possible": False,
                "message": "Your 'Target Weight' suggests a different goal (e.g., weight loss) than your selected 'Goal Type' (e.g., weight gain). Please ensure these settings match."
            }

        # Calculate time needed
        weeks_needed = abs(weight_diff / progress_rate)
        days_needed = weeks_needed * 7

        # Calculate estimated completion date
        today = datetime.now().date()
        estimated_date = today + timedelta(days=math.ceil(days_needed))

        return {
            "weeks": round(weeks_needed, 1),
            "days": round(days_needed),
            "estimated_date": estimated_date.isoformat(),
            "is_possible": True,
        }

    def adjust_macro_distribution(
        self,
        protein: Optional[int] = None,
        carbs: Optional[int] = None,
        fat: Optional[int] = None,
    ) -> MacroCalculatorResponse:
        """
        Calculates total calories and macronutrient distribution based on specified grams.

        The total calories are dynamically determined by the sum of calories from
        the provided protein, carbs, and fat in grams.
        If a macro is not specified, it defaults to 0 grams.
        Carbohydrates will be adjusted to meet MIN_CARBS_GRAMS if below this threshold,
        which will affect the total calories.

        Args:
            protein: Target protein in grams (optional, defaults to 0).
            carbs: Target carbs in grams (optional, defaults to 0).
            fat: Target fat in grams (optional, defaults to 0).

        Returns:
            MacroCalculatorResponse with calculated total calories and macro breakdown.

        Raises:
            MacrosServiceError: If an unexpected error occurs during calculation.
        """
        try:
            protein_g = protein if protein is not None else 0
            carbs_g = carbs if carbs is not None else 0
            fat_g = fat if fat is not None else 0

            # Ensure non-negative values
            protein_g = max(0, protein_g)
            carbs_g = max(0, carbs_g)
            fat_g = max(0, fat_g)

            # Ensure minimum carbohydrates
            carbs_g = max(MIN_CARBS_GRAMS, carbs_g)

            # Calculate calories for each macro
            protein_cals = protein_g * PROTEIN_CALS_PER_GRAM
            carbs_cals = carbs_g * CARB_CALS_PER_GRAM
            fat_cals = fat_g * FAT_CALS_PER_GRAM

            # Calculate total calories
            total_calories = protein_cals + carbs_cals + fat_cals

            return MacroCalculatorResponse(
                calories=total_calories,
                protein=protein_g,
                carbs=carbs_g,
                fat=fat_g,
            )

        except Exception as e:
            logger.error(f"Error adjusting macro distribution: {str(e)}")
            raise MacrosServiceError(f"Error adjusting macro distribution: {str(e)}")

    def save_user_preferences(
        self, user_id: str, macro_targets: MacroCalculatorResponse
    ) -> Dict[str, Any]:
        """
        Save or update user's macro targets in the user_preferences table.

        Args:
            user_id: The user's unique identifier
            macro_targets: The calculated macro targets to save

        Returns:
            Dictionary with the saved preferences data

        Raises:
            MacrosServiceError: If there's an error saving the preferences
        """
        try:
            # Check if user already has preferences
            existing_prefs = self._get_user_preferences(user_id)

            now = datetime.now().isoformat()

            # Prepare data to save
            preferences_data = {
                "user_id": user_id,
                "calorie_target": float(macro_targets.calories),
                "protein_target": float(macro_targets.protein),
                "carbs_target": float(macro_targets.carbs),
                "fat_target": float(macro_targets.fat),
                "dietary_preference": macro_targets.dietary_preference,
                "goal_type": macro_targets.goal_type
            }

            if macro_targets.target_weight:
                preferences_data["target_weight"] = float(macro_targets.target_weight)

            # If user already has preferences, update them
            if existing_prefs:
                result = BaseDatabaseService.subclasses[0]().update_data(
                    table_name="user_preferences",
                    data=preferences_data,
                    cols={"user_id": user_id},
                )
            # Otherwise, insert new preferences
            else:
                preferences_data["created_at"] = now
                result = BaseDatabaseService.subclasses[0]().insert_data(
                    table_name="user_preferences", data=preferences_data
                )

            # Update the user profile to indicate they have macros set
            BaseDatabaseService.subclasses[0]().update_data(
                table_name="user_profiles",
                data={"has_macros": True, "updated_at": now},
                cols={"id": user_id},
            )

            return result

        except Exception as e:
            logger.error(f"Error saving user preferences: {str(e)}")
            raise MacrosServiceError(f"Error saving user preferences: {str(e)}")

    def _get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user's preferences from the database.

        Args:
            user_id: The user's unique identifier

        Returns:
            Dictionary with the user's preferences or None if not found
        """
        try:
            result = BaseDatabaseService.subclasses[0]().select_data(
                table_name="user_preferences", cols={"user_id": user_id}
            )

            if result and len(result) > 0:
                return result[0]
            return None

        except Exception as e:
            logger.error(f"Error retrieving user preferences: {str(e)}")
            return None

    def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a user's preferences from the database.

        Args:
            user_id: The user's unique identifier

        Returns:
            Dictionary with the user's preferences or None if not found

        Raises:
            MacrosServiceError: If there's an error retrieving the preferences
        """
        try:
            return self._get_user_preferences(user_id)
        except Exception as e:
            logger.error(f"Error retrieving user preferences: {str(e)}")
            raise MacrosServiceError(f"Error retrieving user preferences: {str(e)}")


macros_service = MacrosService()
