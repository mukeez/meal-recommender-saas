# app/services/meal_service.py
"""Services for managing meal logging and tracking.

This module provides functions to log meals and track daily nutrition progress.
"""
from typing import Dict, Any, List
import logging
from datetime import datetime, date

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.models.meal import LogMealRequest, LoggedMeal, MacroNutrients, DailyProgressResponse
from app.services.user_service import user_service

logger = logging.getLogger(__name__)


class MealService:
    """Service for managing meal logging and tracking."""

    def __init__(self):
        """Initialize the meal service."""
        self.base_url = settings.SUPABASE_URL
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY

    async def log_meal(self, user_id: str, meal_data: LogMealRequest) -> LoggedMeal:
        """Log a meal for a user.

        Args:
            user_id: ID of the user logging the meal
            meal_data: Details of the meal to log

        Returns:
            The logged meal with additional metadata
        """
        logger.info(f"Logging meal for user: {user_id}")

        try:
            # Prepare meal log data
            meal_record = {
                "user_id": user_id,
                "name": meal_data.name,
                "protein": meal_data.protein,
                "carbs": meal_data.carbs,
                "fat": meal_data.fat,
                "calories": meal_data.calories,
                "meal_time": meal_data.meal_time.isoformat(),
                "created_at": datetime.now().isoformat()
            }

            # Use Supabase REST API to insert meal log
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation"
                    },
                    json=meal_record
                )

                if response.status_code not in (201, 200):
                    error_detail = "Failed to log meal"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Meal logging failed: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to log meal: {error_detail}"
                    )

                # Parse the returned meal log
                logged_meal_data = response.json()[0]
                logged_meal = LoggedMeal(
                    id=logged_meal_data['id'],
                    user_id=logged_meal_data['user_id'],
                    name=logged_meal_data['name'],
                    protein=logged_meal_data['protein'],
                    carbs=logged_meal_data['carbs'],
                    fat=logged_meal_data['fat'],
                    calories=logged_meal_data['calories'],
                    meal_time=datetime.fromisoformat(logged_meal_data['meal_time']),
                    created_at=datetime.fromisoformat(logged_meal_data['created_at'])
                )

                logger.info(f"Meal logged successfully for user: {user_id}")
                return logged_meal

        except httpx.RequestError as e:
            logger.error(f"Request error logging meal: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error logging meal: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error logging meal: {str(e)}"
            )

    async def get_meals_for_today(self, user_id: str) -> List[LoggedMeal]:
        """Retrieve meals logged by the user today.

        Args:
            user_id: ID of the user

        Returns:
            List of meals logged today
        """
        logger.info(f"Fetching today's meals for user: {user_id}")

        try:
            # Get today's date in ISO format
            today_start = datetime.combine(date.today(), datetime.min.time()).isoformat()
            today_end = datetime.combine(date.today(), datetime.max.time()).isoformat()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    params={
                        "user_id": f"eq.{user_id}",
                        "meal_time": f"between.{today_start},{today_end}",
                        "order": "meal_time.desc"
                    }
                )

                if response.status_code not in (200, 201, 204):
                    logger.error(f"Failed to fetch meals: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to retrieve meals"
                    )

                # Parse the meals
                meals_data = response.json()
                meals = [
                    LoggedMeal(
                        id=meal['id'],
                        user_id=meal['user_id'],
                        name=meal['name'],
                        protein=meal['protein'],
                        carbs=meal['carbs'],
                        fat=meal['fat'],
                        calories=meal['calories'],
                        meal_time=datetime.fromisoformat(meal['meal_time']),
                        created_at=datetime.fromisoformat(meal['created_at'])
                    ) for meal in meals_data
                ]

                return meals

        except httpx.RequestError as e:
            logger.error(f"Request error fetching meals: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error fetching meals: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving meals: {str(e)}"
            )

    async def get_daily_progress(self, user_id: str) -> DailyProgressResponse:
        """Calculate daily progress towards macro targets.

        Args:
            user_id: ID of the user

        Returns:
            Daily progress with logged macros and target macros
        """
        logger.info(f"Calculating daily progress for user: {user_id}")

        try:
            # Fetch today's meals
            meals = await self.get_meals_for_today(user_id)

            # Calculate total logged macros
            logged_macros = MacroNutrients(
                calories=sum(meal.calories for meal in meals),
                protein=sum(meal.protein for meal in meals),
                carbs=sum(meal.carbs for meal in meals),
                fat=sum(meal.fat for meal in meals)
            )

            # Fetch user preferences to get targets
            preferences = await user_service.get_user_preferences(user_id)

            # Create target macros
            target_macros = MacroNutrients(
                calories=preferences.get('calorie_target', 2000),
                protein=preferences.get('protein_target', 150),
                carbs=preferences.get('carbs_target', 200),
                fat=preferences.get('fat_target', 70)
            )

            # Calculate progress percentages
            progress_percentage = {
                'calories': min(100, (logged_macros.calories / target_macros.calories) * 100),
                'protein': min(100, (logged_macros.protein / target_macros.protein) * 100),
                'carbs': min(100, (logged_macros.carbs / target_macros.carbs) * 100),
                'fat': min(100, (logged_macros.fat / target_macros.fat) * 100)
            }

            return DailyProgressResponse(
                logged_macros=logged_macros,
                target_macros=target_macros,
                progress_percentage=progress_percentage
            )

        except Exception as e:
            logger.error(f"Unexpected error calculating daily progress: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error calculating daily progress: {str(e)}"
            )


# Create a singleton instance
meal_service = MealService()