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
    ProgressSummary,
    MacroSummary,
    UpdateMealRequest,
    MealSearchRequest,
    MealSearchResponse,
)
from app.services.user_service import user_service
from app.utils.file_upload import upload_file_to_bucket, generate_meal_photo_path, validate_image_file

import traceback

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
            if not self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error"
                )

            # Use current timestamp if not provided
            current_time = datetime.now().time()

            # Determine meal type based on time if not explicitly provided
            meal_type = meal_data.meal_type
            if not meal_type:
                meal_type = self._classify_meal_by_time(current_time)

            
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
                "logging_mode": meal_data.logging_mode,
                "notes": meal_data.notes,
                "photo_url": None,  # Will be updated after meal is created if photo is uploaded
                "serving_unit": meal_data.serving_unit,
                "amount": meal_data.amount,
                "favorite": meal_data.favorite,
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
                # Calculate read_only based on logging_mode
                logging_mode = logged_meal_data.get("logging_mode", "manual")
                read_only = logging_mode in ["barcode", "scanned"]
                
                logged_meal = LoggedMeal(
                    id=logged_meal_data["id"],
                    user_id=logged_meal_data["user_id"],
                    name=logged_meal_data["name"],
                    description=logged_meal_data["description"],
                    protein=logged_meal_data["protein"],
                    carbs=logged_meal_data["carbs"],
                    fat=logged_meal_data["fat"],
                    calories=logged_meal_data["calories"],
                    meal_time=logged_meal_data["meal_time"],
                    meal_type=logged_meal_data.get("meal_type"),
                    logging_mode=logging_mode,
                    photo_url=logged_meal_data.get("photo_url"),
                    created_at=logged_meal_data["created_at"],
                    notes=logged_meal_data.get("notes"),
                    serving_unit=logged_meal_data.get("serving_unit", "grams"),
                    amount=logged_meal_data.get("amount", 1.0),
                    read_only=read_only,
                    favorite=logged_meal_data.get("favorite", False),
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
            if not self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error"
                )
            
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
                    # Calculate read_only based on logging_mode
                    logging_mode = meal.get("logging_mode", "manual")
                    read_only = logging_mode in ["barcode", "scanned"]
                    
                    meals.append(
                        LoggedMeal(
                            id=meal["id"],
                            user_id=meal["user_id"],
                            name=meal["name"],
                            description=meal.get("description"),
                            protein=meal["protein"],
                            carbs=meal["carbs"],
                            fat=meal["fat"],
                            calories=meal["calories"],
                            meal_time=meal["meal_time"],
                            created_at=meal["created_at"],
                            notes=meal.get("notes"),
                            meal_type=meal.get("meal_type"),
                            logging_mode=logging_mode,
                            photo_url=meal.get("photo_url"),
                            serving_unit=meal.get("serving_unit", "grams"),
                            amount=meal.get("amount", 1.0),
                            read_only=read_only,
                            favorite=meal.get("favorite", False),
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
            if not self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error"
                )
            
            # Use the SQL function via RPC call
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params=[
                        ("user_id", f"eq.{user_id}"),
                        ("meal_time", f"gte.{start_date.isoformat()}"),
                        ("meal_time", f"lt.{(end_date + timedelta(days=1)).isoformat()}"),
                        ("order", "meal_time.desc"),
                    ],
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
                    # Calculate read_only based on logging_mode
                    logging_mode = meal.get("logging_mode", "manual")
                    read_only = logging_mode in ["barcode", "scanned"]
                    
                    meals.append(
                        LoggedMeal(
                            id=meal["id"],
                            user_id=meal["user_id"],
                            name=meal["name"],
                            description=meal["description"],
                            protein=meal["protein"],
                            carbs=meal["carbs"],
                            fat=meal["fat"],
                            calories=meal["calories"],
                            meal_time=meal["meal_time"],
                            created_at=meal["created_at"],
                            notes=meal.get("notes"),
                            meal_type=meal.get("meal_type"),
                            logging_mode=logging_mode,
                            photo_url=meal.get("photo_url"),
                            serving_unit=meal.get("serving_unit", "grams"),
                            amount=meal.get("amount", 1.0),
                            read_only=read_only,
                            favorite=meal.get("favorite", False),
                        )
                    )

                logger.info(f"Retrieved {len(meals)} meals for date range")
                return meals

        except Exception as e:
            logger.error(f"Unexpected error fetching meals by date range: {str(e)}")
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving meals: {str(e)}",
            )

    async def get_favorite_meals(self, user_id: str, limit: int = 50) -> List[LoggedMeal]:
        """Retrieve meals marked as favorites by the user.

        Args:
            user_id: ID of the user
            limit: Maximum number of results to return

        Returns:
            List of favorite meals
        """
        logger.info(f"Fetching favorite meals for user: {user_id}")

        try:
            if not self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error"
                )
            
            # Type assertion to help the type checker
            api_key: str = self.api_key

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": api_key,
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    params=[
                        ("user_id", f"eq.{user_id}"),
                        ("favorite", "eq.true"),
                        ("order", "meal_time.desc"),
                        ("limit", str(limit)),
                    ],
                )

                if response.status_code != 200:
                    logger.warning(f"Failed to fetch favorite meals: {response.text}")
                    return []

                meals_data = response.json()
                meals = []

                for meal in meals_data:
                    # Calculate read_only based on logging_mode
                    logging_mode = meal.get("logging_mode", "manual")
                    read_only = logging_mode in ["barcode", "scanned"]
                    
                    meals.append(
                        LoggedMeal(
                            id=meal["id"],
                            user_id=meal["user_id"],
                            name=meal["name"],
                            description=meal.get("description"),
                            protein=meal["protein"],
                            carbs=meal["carbs"],
                            fat=meal["fat"],
                            calories=meal["calories"],
                            meal_time=self._parse_datetime(meal["meal_time"]),
                            created_at=self._parse_datetime(meal["created_at"]),
                            notes=meal.get("notes"),
                            meal_type=meal.get("meal_type"),
                            logging_mode=logging_mode,
                            photo_url=meal.get("photo_url"),
                            serving_unit=meal.get("serving_unit", "grams"),
                            amount=meal.get("amount", 1.0),
                            read_only=read_only,
                            favorite=meal.get("favorite", False),
                        )
                    )

                logger.info(f"Retrieved {len(meals)} favorite meals")
                return meals

        except Exception as e:
            logger.error(f"Unexpected error fetching favorite meals: {str(e)}")
            return []

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
                calories=preferences.get("calorie_target", 0),
                protein=preferences.get("protein_target", 0),
                carbs=preferences.get("carbs_target", 0),
                fat=preferences.get("fat_target", 0),
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
            if not self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error"
                )

            # Type assertion to help the type checker
            api_key: str = self.api_key

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": api_key,
                        "Authorization": f"Bearer {api_key}",
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
        self, user_id: str, period: str
    ) -> ProgressSummary:
        """Generate a progress summary with new aggregation logic based on period.

        Args:
            user_id: ID of the user
            period: Period type (1w, 1m, 3m, 6m, 1y, all)

        Returns:
            ProgressSummary object with period-based aggregation
        """
        logger.info(f"Generating progress summary for user {user_id} with period {period}")

        try:
            # Get the user's preference data for target macros
            preferences = await user_service.get_user_preferences(user_id)
            target_macros = MacroNutrients(
                calories=preferences.get("calorie_target", 0),
                protein=preferences.get("protein_target", 0),
                carbs=preferences.get("carbs_target", 0),
                fat=preferences.get("fat_target", 0),
            )

            # Handle different period types
            period = period.replace(" ", "").lower()
            
            if period == "1w":
                return await self._get_weekly_progress(user_id, target_macros)
            elif period == "1m":
                return await self._get_monthly_weekly_progress(user_id, target_macros)
            elif period == "3m":
                return await self._get_quarterly_progress(user_id, target_macros)
            elif period == "6m":
                return await self._get_six_month_progress(user_id, target_macros)
            elif period == "1y":
                return await self._get_yearly_progress(user_id, target_macros)

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid period parameter: {period}",
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error generating progress summary: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating progress summary",
            )

    async def _get_weekly_progress(self, user_id: str, target_macros: MacroNutrients) -> ProgressSummary:
        """Get progress aggregated by weekdays for current week."""
        today = date.today()
        # Get current week's Monday
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)
        
        # Fetch meals for the current week
        meals = await self.get_meals_by_date_range(user_id, week_start, week_end)
        
        # Group meals by weekday
        weekday_meals = {i: [] for i in range(7)}  # 0=Monday, 6=Sunday
        for meal in meals:
            weekday = meal.meal_time.date().weekday()
            weekday_meals[weekday].append(meal)
        
        # Create weekday labels
        weekday_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        period_macros = []
        total_calories = total_protein = total_carbs = total_fat = 0
        days_with_logs = 0
        
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            day_meals = weekday_meals[i]
            
            daily_calories = sum(meal.calories for meal in day_meals)
            daily_protein = sum(meal.protein for meal in day_meals)
            daily_carbs = sum(meal.carbs for meal in day_meals)
            daily_fat = sum(meal.fat for meal in day_meals)
            
            if daily_calories > 0:
                days_with_logs += 1
                
            period_macros.append(MacroSummary(
                period_label=weekday_labels[i],
                date=day_date,
                calories=daily_calories,
                protein=daily_protein,
                carbs=daily_carbs,
                fat=daily_fat,
            ))
            
            total_calories += daily_calories
            total_protein += daily_protein
            total_carbs += daily_carbs
            total_fat += daily_fat
        
        # Calculate averages
        avg_divisor = max(days_with_logs, 1)
        average_macros = MacroNutrients(
            calories=round(total_calories / avg_divisor, 1),
            protein=round(total_protein / avg_divisor, 1),
            carbs=round(total_carbs / avg_divisor, 1),
            fat=round(total_fat / avg_divisor, 1),
        )
        
        comparison_percentage = self._calculate_comparison_percentage(average_macros, target_macros)
        
        return ProgressSummary(
            period_macros=period_macros,
            average_macros=average_macros,
            target_macros=target_macros,
            comparison_percentage=comparison_percentage,
            start_date=week_start,
            end_date=week_end,
            period_type="weekdays",
            aggregation_period="1w",
            days_with_logs=days_with_logs,
            total_days=7,
        )

    def _calculate_comparison_percentage(self, average_macros: MacroNutrients, target_macros: MacroNutrients) -> Dict[str, float]:
        """Helper method to calculate comparison percentages."""
        return {
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

    async def _get_monthly_weekly_progress(self, user_id: str, target_macros: MacroNutrients) -> ProgressSummary:
        """Get progress aggregated by weeks for current calendar month."""
        import calendar
        
        today = date.today()
        # Get current month boundaries
        month_start = today.replace(day=1)
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        month_end = next_month - timedelta(days=1)
        
        # Fetch meals for the current month
        meals = await self.get_meals_by_date_range(user_id, month_start, month_end)
        
        # Calculate weeks in the month
        week_data = []
        current_date = month_start
        week_num = 1
        
        while current_date <= month_end:
            # Find Monday of current week
            days_since_monday = current_date.weekday()
            week_monday = current_date - timedelta(days=days_since_monday)
            week_sunday = week_monday + timedelta(days=6)
            
            # Only include if week overlaps with current month
            if week_monday <= month_end:
                week_data.append({
                    "label": f"W{week_num}",
                    "start": max(week_monday, month_start),
                    "end": min(week_sunday, month_end)
                })
                week_num += 1
            
            current_date = week_sunday + timedelta(days=1)
            if week_num > 6:  # Safety check
                break
        
        period_macros = []
        total_calories = total_protein = total_carbs = total_fat = 0
        days_with_logs = 0
        
        for week_info in week_data:
            week_start = week_info["start"]
            week_end = week_info["end"]
            week_label = week_info["label"]
            
            # Filter meals for this week
            week_meals = [meal for meal in meals if week_start <= meal.meal_time.date() <= week_end]
            
            weekly_calories = sum(meal.calories for meal in week_meals)
            weekly_protein = sum(meal.protein for meal in week_meals)
            weekly_carbs = sum(meal.carbs for meal in week_meals)
            weekly_fat = sum(meal.fat for meal in week_meals)
            
            # Count days with logs
            week_dates_with_logs = set(meal.meal_time.date() for meal in week_meals)
            days_with_logs += len(week_dates_with_logs)
            
            period_macros.append(MacroSummary(
                period_label=week_label,
                date=week_start,
                calories=weekly_calories,
                protein=weekly_protein,
                carbs=weekly_carbs,
                fat=weekly_fat,
            ))
            
            total_calories += weekly_calories
            total_protein += weekly_protein
            total_carbs += weekly_carbs
            total_fat += weekly_fat
        
        # Calculate averages
        avg_divisor = max(len(week_data), 1)
        average_macros = MacroNutrients(
            calories=round(total_calories / avg_divisor, 1),
            protein=round(total_protein / avg_divisor, 1),
            carbs=round(total_carbs / avg_divisor, 1),
            fat=round(total_fat / avg_divisor, 1),
        )
        
        comparison_percentage = self._calculate_comparison_percentage(average_macros, target_macros)
        
        return ProgressSummary(
            period_macros=period_macros,
            average_macros=average_macros,
            target_macros=target_macros,
            comparison_percentage=comparison_percentage,
            start_date=month_start,
            end_date=month_end,
            period_type="weeks",
            aggregation_period="1m",
            days_with_logs=days_with_logs,
            total_days=(month_end - month_start).days + 1,
        )

    async def _get_quarterly_progress(self, user_id: str, target_macros: MacroNutrients) -> ProgressSummary:
        """Get progress for last 3 complete months."""
        import calendar
        
        today = date.today()
        months_data = []
        
        for i in range(3, 0, -1):  # 3, 2, 1 months ago
            if today.month - i > 0:
                target_month = today.month - i
                target_year = today.year
            else:
                target_month = today.month - i + 12
                target_year = today.year - 1
                
            month_start = date(target_year, target_month, 1)
            month_end = date(target_year, target_month, calendar.monthrange(target_year, target_month)[1])
            
            months_data.append({
                "label": calendar.month_abbr[target_month],
                "start": month_start,
                "end": month_end
            })
        
        return await self._get_monthly_aggregation(user_id, target_macros, months_data, "3m")

    async def _get_six_month_progress(self, user_id: str, target_macros: MacroNutrients) -> ProgressSummary:
        """Get progress for last 6 complete months."""
        import calendar
        
        today = date.today()
        months_data = []
        
        for i in range(6, 0, -1):  # 6, 5, 4, 3, 2, 1 months ago
            if today.month - i > 0:
                target_month = today.month - i
                target_year = today.year
            else:
                target_month = today.month - i + 12
                target_year = today.year - 1
                
            month_start = date(target_year, target_month, 1)
            month_end = date(target_year, target_month, calendar.monthrange(target_year, target_month)[1])
            
            months_data.append({
                "label": calendar.month_abbr[target_month],
                "start": month_start,
                "end": month_end
            })
        
        return await self._get_monthly_aggregation(user_id, target_macros, months_data, "6m")

    async def _get_yearly_progress(self, user_id: str, target_macros: MacroNutrients) -> ProgressSummary:
        """Get progress for current calendar year by months."""
        import calendar
        
        today = date.today()
        current_year = today.year
        months_data = []
        
        for month_num in range(1, 13):
            month_start = date(current_year, month_num, 1)
            month_end = date(current_year, month_num, calendar.monthrange(current_year, month_num)[1])
            
            months_data.append({
                "label": calendar.month_abbr[month_num],
                "start": month_start,
                "end": month_end
            })
        
        return await self._get_monthly_aggregation(user_id, target_macros, months_data, "1y")

    async def _get_monthly_aggregation(self, user_id: str, target_macros: MacroNutrients, months_data: list, period_code: str) -> ProgressSummary:
        """Helper method to aggregate meals by months."""
        overall_start = months_data[0]["start"]
        overall_end = months_data[-1]["end"]
        
        # Fetch all meals for the period
        meals = await self.get_meals_by_date_range(user_id, overall_start, overall_end)
        
        period_macros = []
        total_calories = total_protein = total_carbs = total_fat = 0
        days_with_logs = 0
        
        for month_info in months_data:
            month_start = month_info["start"]
            month_end = month_info["end"]
            month_label = month_info["label"]
            
            # Filter meals for this month
            month_meals = [meal for meal in meals if month_start <= meal.meal_time.date() <= month_end]
            
            monthly_calories = sum(meal.calories for meal in month_meals)
            monthly_protein = sum(meal.protein for meal in month_meals)
            monthly_carbs = sum(meal.carbs for meal in month_meals)
            monthly_fat = sum(meal.fat for meal in month_meals)
            
            # Count days with logs in this month
            month_dates_with_logs = set(meal.meal_time.date() for meal in month_meals)
            days_with_logs += len(month_dates_with_logs)
            
            period_macros.append(MacroSummary(
                period_label=month_label,
                date=month_start,
                calories=monthly_calories,
                protein=monthly_protein,
                carbs=monthly_carbs,
                fat=monthly_fat,
            ))
            
            total_calories += monthly_calories
            total_protein += monthly_protein
            total_carbs += monthly_carbs
            total_fat += monthly_fat
        
        # Calculate averages
        avg_divisor = max(len(months_data), 1)
        average_macros = MacroNutrients(
            calories=round(total_calories / avg_divisor, 1),
            protein=round(total_protein / avg_divisor, 1),
            carbs=round(total_carbs / avg_divisor, 1),
            fat=round(total_fat / avg_divisor, 1),
        )
        
        comparison_percentage = self._calculate_comparison_percentage(average_macros, target_macros)
        
        return ProgressSummary(
            period_macros=period_macros,
            average_macros=average_macros,
            target_macros=target_macros,
            comparison_percentage=comparison_percentage,
            start_date=overall_start,
            end_date=overall_end,
            period_type="months",
            aggregation_period=period_code,
            days_with_logs=days_with_logs,
            total_days=(overall_end - overall_start).days + 1,
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
            if not self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error"
                )

            # Type assertion to help the type checker
            api_key: str = self.api_key

            # First, verify the meal belongs to the user
            async with httpx.AsyncClient() as client:
                # Check if meal exists and belongs to user
                response = await client.get(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": api_key,
                        "Authorization": f"Bearer {api_key}",
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
                        "apikey": api_key,
                        "Authorization": f"Bearer {api_key}",
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
                # Calculate read_only based on logging_mode
                logging_mode = updated_meal_data.get("logging_mode", "manual")
                read_only = logging_mode in ["barcode", "scanned"]
                
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
                    logging_mode=logging_mode,
                    photo_url=updated_meal_data.get("photo_url"),
                    serving_unit=updated_meal_data.get("serving_unit", "grams"),
                    amount=updated_meal_data.get("amount", 1.0),
                    read_only=read_only,
                    favorite=updated_meal_data.get("favorite", False),
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
            if not self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error"
                )

            # Type assertion to help the type checker
            api_key: str = self.api_key

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/v1/meal_logs",
                    headers={
                        "apikey": api_key,
                        "Authorization": f"Bearer {api_key}",
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
                        "apikey": api_key,
                        "Authorization": f"Bearer {api_key}",
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

    async def upload_meal_photo(
        self, user_id: str, meal_id: str, file_content: bytes, content_type: str
    ) -> str:
        """Upload a meal photo to Supabase storage.

        Args:
            user_id: ID of the user
            meal_id: ID of the meal
            file_content: Image file content as bytes
            content_type: MIME type of the image

        Returns:
            Public URL to the uploaded meal photo

        Raises:
            HTTPException: If there is an error uploading the photo
        """

        logger.info(f"Uploading meal photo for user {user_id}, meal {meal_id}")

        # Validate the image file
        validate_image_file(None, content_type)

        # Generate the file path
        file_extension = "png" if content_type == "image/png" else "jpg"
        file_path = generate_meal_photo_path(user_id, meal_id, file_extension)

        # Upload using the generalized function
        return await upload_file_to_bucket(file_content, file_path, content_type)

    async def update_meal_photo_url(self, user_id: str, meal_id: str, photo_url: str) -> None:
        """Update the photo URL for a meal in the database.

        Args:
            user_id: ID of the user
            meal_id: ID of the meal
            photo_url: URL of the uploaded photo

        Raises:
            HTTPException: If there is an error updating the meal
        """
        logger.info(f"Updating photo URL for meal {meal_id}")

        try:
            if not self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error"
                )

            async with httpx.AsyncClient() as client:
                response = await client.patch(
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
                    json={"photo_url": photo_url},
                )

                if response.status_code not in (200, 201, 204):
                    logger.error(f"Failed to update meal photo URL: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update meal photo",
                    )

                logger.info(f"Meal photo URL updated successfully for meal: {meal_id}")

        except httpx.RequestError as e:
            logger.error(f"Request error updating meal photo URL: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Error communicating with database",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating meal photo URL: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error updating meal photo",
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

        if isinstance(dt_str, str):
            if "Z" in dt_str:
                dt_str = dt_str.replace("Z", "+00:00")

        try:
            return datetime.fromisoformat(dt_str)
        except:
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

    async def search_meals(self, user_id: str, search_request: MealSearchRequest) -> MealSearchResponse:
        """Search for meals in user's logged meals and suggest products if no matches found.

        Args:
            user_id: ID of the user
            search_request: Search parameters including query, filters, and pagination

        Returns:
            MealSearchResponse with logged meals and/or product suggestions
        """
        logger.info(f"Searching meals for user {user_id} with query: '{search_request.query}'")

        try:
            if not self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error"
                )

            # Search in logged meals
            logged_meals = await self._search_logged_meals(user_id, search_request)

            response = MealSearchResponse(
                results=logged_meals,
                total_results=len(logged_meals),
                search_query=search_request.query
            )

            logger.info(f"Search completed: {len(logged_meals)} meals found")
            return response

        except Exception as e:
            logger.error(f"Error searching meals: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error searching meals: {str(e)}",
            )

    async def _search_logged_meals(self, user_id: str, search_request: MealSearchRequest) -> List[LoggedMeal]:
        """Search for logged meals based on query and filters.

        Args:
            user_id: ID of the user
            search_request: Search parameters

        Returns:
            List of matching logged meals
        """
        try:
            if not self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error"
                )
            
            # Type assertion to help the type checker
            api_key: str = self.api_key

            # Process the query - handle quoted strings and clean up
            search_query = self._process_search_query(search_request.query)

            # Build base query parameters (common to both searches)
            base_params = [
                ("user_id", f"eq.{user_id}"),
                ("order", "meal_time.desc"),
            ]

            # Add meal type filter if specified
            if search_request.meal_type:
                base_params.append(("meal_type", f"eq.{search_request.meal_type}"))

            # Add date range filters if specified
            if search_request.start_date:
                base_params.append(("meal_time", f"gte.{search_request.start_date.isoformat()}"))
            
            if search_request.end_date:
                # Add one day to make end_date inclusive
                end_date_inclusive = search_request.end_date + timedelta(days=1)
                base_params.append(("meal_time", f"lt.{end_date_inclusive.isoformat()}"))

            # Add favorites filter if specified
            if search_request.favorites_only is not None:
                base_params.append(("favorite", f"eq.{search_request.favorites_only}"))

            all_meals = []
            meal_ids_seen = set()

            async with httpx.AsyncClient() as client:
                # Search by name if query is meaningful
                if search_query.strip() and search_query not in ["*", "**"]:
                    # Search in name field
                    name_params = base_params.copy()
                    name_params.append(("name", f"ilike.*{search_query}*"))
                    name_params.append(("limit", str(search_request.limit)))

                    response = await client.get(
                        f"{self.base_url}/rest/v1/meal_logs",
                        headers={
                            "apikey": api_key,
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        params=name_params,  # type: ignore
                    )

                    if response.status_code == 200:
                        name_meals = response.json()
                        for meal in name_meals:
                            if meal["id"] not in meal_ids_seen:
                                all_meals.append(meal)
                                meal_ids_seen.add(meal["id"])

                    # Search in description field if we haven't reached the limit
                    if len(all_meals) < search_request.limit:
                        remaining_limit = search_request.limit - len(all_meals)
                        desc_params = base_params.copy()
                        desc_params.append(("description", f"ilike.*{search_query}*"))
                        desc_params.append(("limit", str(remaining_limit)))

                        response = await client.get(
                            f"{self.base_url}/rest/v1/meal_logs",
                            headers={
                                "apikey": api_key,
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json",
                            },
                            params=desc_params,  # type: ignore
                        )

                        if response.status_code == 200:
                            desc_meals = response.json()
                            for meal in desc_meals:
                                if meal["id"] not in meal_ids_seen and len(all_meals) < search_request.limit:
                                    all_meals.append(meal)
                                    meal_ids_seen.add(meal["id"])

                else:
                    # No search query, just get all meals with filters
                    params = base_params.copy()
                    params.append(("limit", str(search_request.limit)))

                    response = await client.get(
                        f"{self.base_url}/rest/v1/meal_logs",
                        headers={
                            "apikey": api_key,
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        params=params,  # type: ignore
                    )

                    if response.status_code == 200:
                        all_meals = response.json()


                meals = []
                for meal in all_meals:
                    # Calculate read_only based on logging_mode
                    logging_mode = meal.get("logging_mode", "manual")
                    read_only = logging_mode in ["barcode", "scanned"]
                    
                    meals.append(
                        LoggedMeal(
                            id=meal["id"],
                            user_id=meal["user_id"],
                            name=meal["name"],
                            description=meal.get("description"),
                            protein=meal["protein"],
                            carbs=meal["carbs"],
                            fat=meal["fat"],
                            calories=meal["calories"],
                            meal_time=meal["meal_time"],
                            created_at=meal["created_at"],
                            notes=meal.get("notes"),
                            meal_type=meal.get("meal_type"),
                            logging_mode=logging_mode,
                            photo_url=meal.get("photo_url"),
                            serving_unit=meal.get("serving_unit", "grams"),
                            amount=meal.get("amount", 1.0),
                            read_only=read_only,
                            favorite=meal.get("favorite", False),
                        )
                    )

                return meals

        except Exception as e:
            logger.error(f"Error searching logged meals: {str(e)}")
            return []

    def _process_search_query(self, query: str) -> str:
        """Process the search query to handle quoted strings and clean up input.
        
        Args:
            query: Raw search query from user input
            
        Returns:
            Cleaned search query ready for database search
        """
        if not query:
            return ""
        
        # Trim initial whitespace
        query = query.strip()
        
        # Handle nested quotes like '"Oat Meal"' or "'Oat Meal'"
        # First remove outer quotes if present
        if (query.startswith('"') and query.endswith('"')) or (query.startswith("'") and query.endswith("'")):
            query = query[1:-1]
        
        # Then remove inner quotes if present (handle the nested case)
        if (query.startswith('"') and query.endswith('"')) or (query.startswith("'") and query.endswith("'")):
            query = query[1:-1]
        
        # Handle escaped quotes within the string
        query = query.replace('\\"', '"').replace("\\'", "'")
        
        # Trim whitespace again after quote removal
        query = query.strip()
        
        return query


meal_service = MealService()
