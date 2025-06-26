"""API endpoints for meal logging and tracking functionality.

This module contains the FastAPI routes for logging meals and tracking daily progress.
"""

import logging
from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import List
from datetime import date, timedelta
from typing import Optional

from app.api.auth_guard import auth_guard
from app.models.meal import (
    LogMealRequest,
    LoggedMeal,
    MealSuggestionRequest,
    MealSuggestionResponse,
    DailyProgressResponse,
    ProgressSummary,
    UpdateMealRequest,
    UpdateMealResponse,
    DeleteMealResponse,
)
from app.services.meal_service import meal_service
from app.services.meal_llm_service import meal_llm_service
from app.services.restaurant_service import restaurant_service
import traceback


router = APIRouter()

logger = logging.getLogger(__name__)


@router.post(
    "/suggest-meals",
    response_model=MealSuggestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get meal suggestions based on macro requirements",
    description="Get personalized meal suggestions based on macro requirements. Returns a list of meal suggestions from restaurants in the specified location.",
)
async def suggest_meals(
    meal_request: MealSuggestionRequest, user=Depends(auth_guard)
) -> MealSuggestionResponse:
    """Get personalized meal suggestions based on macro requirements.

    This endpoint takes the user's location and macro requirements and returns
    a list of meal suggestions from restaurants in the specified location.

    Args:
        meal_request: The meal suggestion request with location and macro targets
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        A response object containing a list of meal suggestions

    Raises:
        HTTPException: If there is an error processing the request
    """
    try:
        # Extract user ID from the authenticated user
        user_id = user.get("sub")

    

        # get restaurants for the user's location
        restaurants = await restaurant_service.find_restaurants_for_location(
            location=meal_request.location,
            latitude=meal_request.latitude,
            longitude=meal_request.longitude,
        )

        meal_suggestions = await meal_llm_service(
            request=meal_request, restaurants=restaurants
        ).get_meal_suggestions()
        return meal_suggestions

    except Exception as e:
        logger.error(f"Error generating meal suggestions for user:{user_id}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating meal suggestions",
        )


@router.post(
    "/add",
    response_model=LoggedMeal,
    status_code=status.HTTP_201_CREATED,
    summary="Log a meal",
    description="Log a meal with its nutritional details for the current user. Meal type is automatically classified based on time of day.",
)
async def log_meal(
    request: Request, meal_data: LogMealRequest, user=Depends(auth_guard)
) -> LoggedMeal:
    """Log a meal for the current user with automatic meal type classification.

    Args:
        request: The incoming FastAPI request
        meal_data: Details of the meal to log
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        The logged meal with additional metadata including meal_type

    Raises:
        HTTPException: If there is an error logging the meal
    """
    try:
        user_id = user.get("sub")

        logged_meal = await meal_service.log_meal(user_id, meal_data)
        return logged_meal

    except Exception as e:
        logger.error(f"Error logging meal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error logging meal: {str(e)}",
        )


@router.get(
    "/today",
    response_model=List[LoggedMeal],
    status_code=status.HTTP_200_OK,
    summary="Get today's meals",
    description="Retrieve all meals logged by the current user for today.",
)
async def get_today_meals(
    request: Request, user=Depends(auth_guard)
) -> List[LoggedMeal]:
    """Retrieve meals logged by the current user today.

    Args:
        request: The incoming FastAPI request
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        List of meals logged today

    Raises:
        HTTPException: If there is an error retrieving meals
    """
    try:
        user_id = user.get("sub")

        today_meals = await meal_service.get_meals_for_today(user_id)
        return today_meals

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving today's meals: {str(e)}",
        )


@router.get(
    "/progress/today",
    response_model=DailyProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Get daily progress",
    description="Calculate and return daily macro progress for the current user.",
)
async def get_daily_progress(
    request: Request, user=Depends(auth_guard)
) -> DailyProgressResponse:
    """Calculate daily macro progress for the current user."""
    try:
        user_id = user.get("sub")

        daily_progress = await meal_service.get_daily_progress(user_id)
        return daily_progress

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating daily progress: {str(e)}",
        )


@router.get(
    "/progress",
    response_model=ProgressSummary,
    status_code=status.HTTP_200_OK,
    summary="Get progress data for a date range",
    description="Retrieve macro intake progress data for a specified date range.",
)
async def get_progress(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    period: Optional[str] = None,
    user=Depends(auth_guard),
) -> ProgressSummary:
    """Retrieve macro intake progress data for a specified date range.

    Args:
        start_date: Start date for the progress data (optional if period is provided)
        end_date: End date for the progress data (optional, defaults to today)
        period: Predefined period (1W, 1M, 3M, 6M, 1Y, All) - overrides start_date
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        Progress summary with daily breakdowns, averages, and comparison to goals

    Raises:
        HTTPException: If there is an error retrieving the progress data
    """
    try:
        user_id = user.get("sub")

        # Set end_date to today if not provided
        if not end_date:
            end_date = date.today()

        # Handle period parameter (overrides start_date)
        if period:
            today = date.today()
            if period == "1W":
                start_date = today - timedelta(days=7)
            elif period == "1M":
                start_date = today - timedelta(days=30)
            elif period == "3M":
                start_date = today - timedelta(days=90)
            elif period == "6M":
                start_date = today - timedelta(days=180)
            elif period == "1Y":
                start_date = today - timedelta(days=365)
            elif period == "All":

                start_date = await meal_service.get_first_meal_date(user_id)
                if not start_date:
                    start_date = today - timedelta(days=30)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid period parameter: {period}",
                )

        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Ensure start_date is before or equal to end_date
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before or equal to end date",
            )

        progress_summary = await meal_service.get_progress_summary(
            user_id, start_date, end_date
        )
        return progress_summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving progress data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving progress data: {str(e)}",
        )


@router.put(
    "/{meal_id}",
    response_model=UpdateMealResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a meal",
    description="Update an existing logged meal for the current user.",
)
async def update_meal(
    meal_id: str,
    meal_data: UpdateMealRequest,
    user=Depends(auth_guard),
) -> UpdateMealResponse:
    """Update an existing logged meal for the current user.

    Args:
        meal_id: ID of the meal to update
        meal_data: Updated meal details
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        UpdateMealResponse with success message and updated meal data

    Raises:
        HTTPException: If there is an error updating the meal
    """
    try:
        user_id = user.get("sub")

        updated_meal = await meal_service.update_meal(user_id, meal_id, meal_data)
        return UpdateMealResponse(
            message="Meal updated successfully",
            meal=updated_meal
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating meal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating meal: {str(e)}",
        )


@router.delete(
    "/{meal_id}",
    response_model=DeleteMealResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a meal",
    description="Delete an existing logged meal for the current user.",
)
async def delete_meal(
    meal_id: str,
    user=Depends(auth_guard),
) -> DeleteMealResponse:
    """Delete an existing logged meal for the current user.

    Args:
        meal_id: ID of the meal to delete
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        DeleteMealResponse with success message and deleted meal ID

    Raises:
        HTTPException: If there is an error deleting the meal
    """
    try:
        user_id = user.get("sub")

        deleted_meal_id = await meal_service.delete_meal(user_id, meal_id)
        return DeleteMealResponse(
            message="Meal deleted successfully",
            meal_id=deleted_meal_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting meal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting meal: {str(e)}",
        )
