"""Services for managing meal logging and tracking.

This module provides functions to log meals and track daily nutrition progress.
"""
import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict
from datetime import datetime, date, time, timedelta

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.meal import (
    MealType,
    LogMealRequest,
    LoggedMeal,
    MacroNutrients,
    DailyProgressResponse,
    DailyMacroSummary,
    ProgressSummary,
    UpdateMealRequest,
    UpdateMealResponse,
    DeleteMealResponse,
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
            # Use current timestamp if not provided
            current_time = datetime.now().time()

            # Determine meal type based on time if not explicitly provided
            meal_type = meal_data.meal_type
            if not meal_type:
                meal_type = self._classify_meal_by_time(current_time)

            # Generate timestamp in ISO format
            timestamp = datetime.now().isoformat()

            # Create the meal entry
            meal_entry = {
                "user_id": user_id,
                "name": meal_data.name,
                "description": meal_data.description,
                "calories": meal_data.calories,
                "protein": meal_data.protein,
                "carbs": meal_data.carbs,
                "fat": meal_data.fat,
                "meal_time": timestamp,
                "meal_type": meal_type,
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
                    json=meal_entry,
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
                    description=logged_meal_data["description"],
                    protein=logged_meal_data["protein"],
                    carbs=logged_meal_data["carbs"],
                    fat=logged_meal_data["fat"],
                    calories=logged_meal_data["calories"],
                    meal_time=self._parse_datetime(logged_meal_data["meal_time"]),
                    created_at=self._parse_datetime(logged_meal_data["created_at"]),
                    notes=logged_meal_data.get("notes"),
                    meal_type=logged_meal_data.get("meal_type"),
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
                            meal_type=meal.get("meal_type"),
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
                            meal_type=meal.get("meal_type"),
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

    async def get_first_meal_date(self, user_id: str) -> Optional[date]:
        """Get the date of the first meal logged by the user.

        Args:
            user_id: ID of the user

        Returns:
            Date of the first logged meal, or None if no meals exist
        """
        logger.info(f"Fetching first meal date for user: {user_id}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={
                        "user_id": f"eq.{user_id}",
                        "order": "created_at.asc",
                        "limit": 1,
                    },
                )

                if response.status_code != 200:
                    logger.warning(f"Failed to fetch first meal date: {response.text}")
                    return None

                meals_data = response.json()
                if not meals_data:
                    return None

                first_meal = meals_data[0]
                first_date = self._parse_datetime(first_meal["created_at"]).date()
                return first_date

        except Exception as e:
            logger.error(f"Error fetching first meal date: {str(e)}")
            return None

    async def get_progress_summary(
        self, user_id: str, start_date: date, end_date: date
    ) -> ProgressSummary:
        """Generate a progress summary for the specified date range.

        Args:
            user_id: ID of the user
            start_date: Start date for the summary
            end_date: End date for the summary

        Returns:
            ProgressSummary object with daily breakdowns, averages, and comparison to goals
        """
        logger.info(
            f"Generating progress summary for user {user_id} from {start_date} to {end_date}"
        )

        try:
            # Get the user's preference data for target macros
            preferences = await user_service.get_user_preferences(user_id)

            # Set target macros from user preferences
            target_macros = MacroNutrients(
                calories=preferences.get("calorie_target", 2000),
                protein=preferences.get("protein_target", 150),
                carbs=preferences.get("carbs_target", 200),
                fat=preferences.get("fat_target", 70),
            )

            # Fetch meals within the date range
            meals = await self.get_meals_by_date_range(user_id, start_date, end_date)

            # Group meals by date
            daily_meals = defaultdict(list)
            for meal in meals:
                meal_date = meal.meal_time.date()
                daily_meals[meal_date].append(meal)

            # Create a list of all dates in the range
            all_dates = []
            current_date = start_date
            while current_date <= end_date:
                all_dates.append(current_date)
                current_date += timedelta(days=1)

            # Calculate daily macros for each date
            daily_macros = []
            total_calories = 0
            total_protein = 0
            total_carbs = 0
            total_fat = 0

            for day in all_dates:
                day_meals = daily_meals.get(day, [])

                daily_calories = sum(meal.calories for meal in day_meals)
                daily_protein = sum(meal.protein for meal in day_meals)
                daily_carbs = sum(meal.carbs for meal in day_meals)
                daily_fat = sum(meal.fat for meal in day_meals)

                daily_macros.append(
                    DailyMacroSummary(
                        date=day,
                        calories=daily_calories,
                        protein=daily_protein,
                        carbs=daily_carbs,
                        fat=daily_fat,
                    )
                )

                total_calories += daily_calories
                total_protein += daily_protein
                total_carbs += daily_carbs
                total_fat += daily_fat

            # Calculate averages
            days_with_logs = len([d for d in daily_macros if d.calories > 0])
            total_days = len(all_dates)

            # Avoid division by zero
            avg_divisor = max(days_with_logs, 1)

            average_macros = MacroNutrients(
                calories=round(total_calories / avg_divisor, 1),
                protein=round(total_protein / avg_divisor, 1),
                carbs=round(total_carbs / avg_divisor, 1),
                fat=round(total_fat / avg_divisor, 1),
            )

            # Calculate comparison percentages
            comparison_percentage = {
                "calories": round(
                    (average_macros.calories / target_macros.calories * 100)
                    if target_macros.calories
                    else 0,
                    1,
                ),
                "protein": round(
                    (average_macros.protein / target_macros.protein * 100)
                    if target_macros.protein
                    else 0,
                    1,
                ),
                "carbs": round(
                    (average_macros.carbs / target_macros.carbs * 100)
                    if target_macros.carbs
                    else 0,
                    1,
                ),
                "fat": round(
                    (average_macros.fat / target_macros.fat * 100)
                    if target_macros.fat
                    else 0,
                    1,
                ),
            }

            return ProgressSummary(
                daily_macros=daily_macros,
                average_macros=average_macros,
                target_macros=target_macros,
                comparison_percentage=comparison_percentage,
                start_date=start_date,
                end_date=end_date,
                days_with_logs=days_with_logs,
                total_days=total_days,
            )

        except Exception as e:
            logger.error(f"Error generating progress summary: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating progress summary",
            )

    async def update_meal(self, user_id: str, meal_id: str, meal_data: "UpdateMealRequest") -> LoggedMeal:
        """Update a logged meal for a user.

        Args:
            user_id: ID of the user updating the meal
            meal_id: ID of the meal to update
            meal_data: Updated meal details

        Returns:
            The updated meal with additional metadata
        """
        logger.info(f"Updating meal {meal_id} for user: {user_id}")

        try:
            # First, verify the meal belongs to the user
            async with httpx.AsyncClient() as client:
                # Check if meal exists and belongs to user
                response = await client.get(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={
                        "id": f"eq.{meal_id}",
                        "user_id": f"eq.{user_id}",
                    },
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to verify meal ownership",
                    )

                meals_data = response.json()
                if not meals_data:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Meal not found or does not belong to user",
                    )

            # Prepare update data (only include non-None values)
            update_data = {}
            for field, value in meal_data.model_dump(exclude_unset=True).items():
                if value is not None:
                    if field == "meal_time" and isinstance(value, datetime):
                        update_data[field] = value.isoformat()
                    else:
                        update_data[field] = value

            if not update_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No valid fields to update",
                )

            # Update the meal
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    params={"id": f"eq.{meal_id}"},
                    json=update_data,
                )

                if response.status_code not in (200, 201):
                    error_detail = "Failed to update meal"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Meal update failed: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to update meal: {error_detail}",
                    )

                updated_meal_data = response.json()[0]
                updated_meal = LoggedMeal(
                    id=updated_meal_data["id"],
                    user_id=updated_meal_data["user_id"],
                    name=updated_meal_data["name"],
                    description=updated_meal_data["description"],
                    protein=updated_meal_data["protein"],
                    carbs=updated_meal_data["carbs"],
                    fat=updated_meal_data["fat"],
                    calories=updated_meal_data["calories"],
                    meal_time=self._parse_datetime(updated_meal_data["meal_time"]),
                    created_at=self._parse_datetime(updated_meal_data["created_at"]),
                    notes=updated_meal_data.get("notes"),
                    meal_type=updated_meal_data.get("meal_type"),
                )

                logger.info(f"Meal {meal_id} updated successfully for user: {user_id}")
                return updated_meal

        except HTTPException:
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error updating meal: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error updating meal: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error updating meal: {str(e)}",
            )

    async def delete_meal(self, user_id: str, meal_id: str) -> str:
        """Delete a logged meal for a user.

        Args:
            user_id: ID of the user deleting the meal
            meal_id: ID of the meal to delete

        Returns:
            The ID of the deleted meal
        """
        logger.info(f"Deleting meal {meal_id} for user: {user_id}")

        try:
            async with httpx.AsyncClient() as client:
                # First, verify the meal belongs to the user
                response = await client.get(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={
                        "id": f"eq.{meal_id}",
                        "user_id": f"eq.{user_id}",
                    },
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to verify meal ownership",
                    )

                meals_data = response.json()
                if not meals_data:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Meal not found or does not belong to user",
                    )

                # Delete the meal
                response = await client.delete(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"id": f"eq.{meal_id}"},
                )

                if response.status_code not in (200, 201, 204):
                    error_detail = "Failed to delete meal"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Meal deletion failed: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to delete meal: {error_detail}",
                    )

                logger.info(f"Meal {meal_id} deleted successfully for user: {user_id}")
                return meal_id

        except HTTPException:
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error deleting meal: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error deleting meal: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error deleting meal: {str(e)}",
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

    def _classify_meal_by_time(self, current_time: time) -> MealType:
        """
        Classify a meal based on the time of day.

        Args:
            current_time: The time to classify

        Returns:
            MealType enum value corresponding to the time of day
        """
        # Breakfast: 4:00 AM – 10:59 AM
        breakfast_start = time(4, 0)
        breakfast_end = time(10, 59)

        # Lunch: 11:00 AM – 3:59 PM
        lunch_start = time(11, 0)
        lunch_end = time(15, 59)

        # Dinner: 4:00 PM – 10:00 PM
        dinner_start = time(16, 0)
        dinner_end = time(22, 0)

        if breakfast_start <= current_time <= breakfast_end:
            return MealType.BREAKFAST
        elif lunch_start <= current_time <= lunch_end:
            return MealType.LUNCH
        elif dinner_start <= current_time <= dinner_end:
            return MealType.DINNER
        else:
            return MealType.OTHER


meal_service = MealService()
