"""Services for managing meal logging and tracking.

This module provides functions to log meals and track daily nutrition progress.
"""

from typing import Dict, Any, List
import logging
from datetime import datetime, date

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.meal import (
    LogMealRequest,
    LoggedMeal,
    MacroNutrients,
    DailyProgressResponse,
)
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
            meal_record = {
                "user_id": user_id,
                "name": meal_data.name,
                "protein": meal_data.protein,
                "carbs": meal_data.carbs,
                "fat": meal_data.fat,
                "calories": meal_data.calories,
                "meal_time": meal_data.meal_time.isoformat(),
                "created_at": datetime.now().isoformat(),
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    json=meal_record,
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
                        detail=f"Failed to log meal: {error_detail}",
                    )

                logged_meal_data = response.json()[0]
                logged_meal = LoggedMeal(
                    id=logged_meal_data["id"],
                    user_id=logged_meal_data["user_id"],
                    name=logged_meal_data["name"],
                    protein=logged_meal_data["protein"],
                    carbs=logged_meal_data["carbs"],
                    fat=logged_meal_data["fat"],
                    calories=logged_meal_data["calories"],
                    meal_time=self._parse_datetime(logged_meal_data["meal_time"]),
                    created_at=self._parse_datetime(logged_meal_data["created_at"]),
                    notes=logged_meal_data.get("notes"),
                )

                logger.info(f"Meal logged successfully for user: {user_id}")
                return logged_meal

        except httpx.RequestError as e:
            logger.error(f"Request error logging meal: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error logging meal: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error logging meal: {str(e)}",
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
            # Use the SQL function via RPC call
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/rest/v1/rpc/query_todays_meals",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"user_id_param": user_id},
                )

                if response.status_code == 404:
                    logger.warning("RPC function not found, using fallback query")
                    today = date.today().isoformat()

                    response = await client.get(
                        f"{self.base_url}/rest/v1/meal_logs",
                        headers={
                            "apikey": self.api_key,
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        params={
                            "user_id": f"eq.{user_id}",
                            "created_at": f"ilike.{today}%",
                            "order": "meal_time.desc",
                        },
                    )

                if response.status_code not in (200, 201, 204):
                    logger.error(f"Failed to fetch meals: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to retrieve meals: {response.text}",
                    )

                meals_data = response.json()
                meals = []

                for meal in meals_data:
                    meals.append(
                        LoggedMeal(
                            id=meal["id"],
                            user_id=meal["user_id"],
                            name=meal["name"],
                            protein=meal["protein"],
                            carbs=meal["carbs"],
                            fat=meal["fat"],
                            calories=meal["calories"],
                            meal_time=self._parse_datetime(meal["meal_time"]),
                            created_at=self._parse_datetime(meal["created_at"]),
                            notes=meal.get("notes"),
                        )
                    )

                logger.info(f"Retrieved {len(meals)} meals for today")
                return meals

        except Exception as e:
            logger.error(f"Unexpected error fetching meals: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving meals: {str(e)}",
            )

    async def get_meals_by_date_range(
        self, user_id: str, start_date: date, end_date: date
    ) -> List[LoggedMeal]:
        """Retrieve meals logged by the user within a date range.

        Args:
            user_id: ID of the user
            start_date: Start date for the range (inclusive)
            end_date: End date for the range (inclusive)

        Returns:
            List of meals logged within the date range
        """
        logger.info(
            f"Fetching meals for user {user_id} from {start_date} to {end_date}"
        )

        try:
            # Use the SQL function via RPC call
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/rest/v1/rpc/query_meals_by_date_range",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "user_id_param": user_id,
                        "start_date_param": start_date.isoformat(),
                        "end_date_param": end_date.isoformat(),
                    },
                )

                if response.status_code not in (200, 201, 204):
                    logger.error(f"Failed to fetch meals: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to retrieve meals: {response.text}",
                    )

                # Parse the meals
                meals_data = response.json()
                meals = []

                for meal in meals_data:
                    meals.append(
                        LoggedMeal(
                            id=meal["id"],
                            user_id=meal["user_id"],
                            name=meal["name"],
                            protein=meal["protein"],
                            carbs=meal["carbs"],
                            fat=meal["fat"],
                            calories=meal["calories"],
                            meal_time=self._parse_datetime(meal["meal_time"]),
                            created_at=self._parse_datetime(meal["created_at"]),
                            notes=meal.get("notes"),
                        )
                    )

                logger.info(f"Retrieved {len(meals)} meals for date range")
                return meals

        except Exception as e:
            logger.error(f"Unexpected error fetching meals by date range: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving meals: {str(e)}",
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

            logged_macros = MacroNutrients(
                calories=sum(meal.calories for meal in meals),
                protein=sum(meal.protein for meal in meals),
                carbs=sum(meal.carbs for meal in meals),
                fat=sum(meal.fat for meal in meals),
            )

            preferences = await user_service.get_user_preferences(user_id)

            target_macros = MacroNutrients(
                calories=preferences.get("calorie_target", 2000),
                protein=preferences.get("protein_target", 150),
                carbs=preferences.get("carbs_target", 200),
                fat=preferences.get("fat_target", 70),
            )

            progress_percentage = {
                "calories": min(
                    100,
                    (
                        (logged_macros.calories / target_macros.calories * 100)
                        if target_macros.calories
                        else 0
                    ),
                ),
                "protein": min(
                    100,
                    (
                        (logged_macros.protein / target_macros.protein * 100)
                        if target_macros.protein
                        else 0
                    ),
                ),
                "carbs": min(
                    100,
                    (
                        (logged_macros.carbs / target_macros.carbs * 100)
                        if target_macros.carbs
                        else 0
                    ),
                ),
                "fat": min(
                    100,
                    (
                        (logged_macros.fat / target_macros.fat * 100)
                        if target_macros.fat
                        else 0
                    ),
                ),
            }

            return DailyProgressResponse(
                logged_macros=logged_macros,
                target_macros=target_macros,
                progress_percentage=progress_percentage,
            )

        except Exception as e:
            logger.error(f"Unexpected error calculating daily progress: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error calculating daily progress: {str(e)}",
            )

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse a datetime string, handling timezone information.

        Args:
            dt_str: Datetime string to parse

        Returns:
            Parsed datetime object
        """
        if not dt_str:
            return datetime.now()

        if "Z" in dt_str:
            dt_str = dt_str.replace("Z", "+00:00")

        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            logger.warning(f"Could not parse datetime: {dt_str}")
            return datetime.now()


meal_service = MealService()
