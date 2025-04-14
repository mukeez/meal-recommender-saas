"""API endpoints for meal logging and tracking functionality.

This module contains the FastAPI routes for logging meals and tracking daily progress.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import List

from app.api.auth_guard import auth_guard
from app.models.meal import (
    LogMealRequest,
    LoggedMeal,
    MealSuggestionRequest,
    MealSuggestionResponse,
    DailyProgressResponse
)
from app.services.meal_service import meal_service
from app.services.llm_service import ai_service


router = APIRouter()


@router.post(
    "/suggest-meals",
    response_model=MealSuggestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get meal suggestions based on macro requirements",
    description="Get personalized meal suggestions based on macro requirements. Returns a list of meal suggestions from restaurants in the specified location.",
)
async def suggest_meals(
        meal_request: MealSuggestionRequest,
        user=Depends(auth_guard)
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

        meal_suggestions = await ai_service.get_meal_suggestions(meal_request)
        return MealSuggestionResponse(meals=meal_suggestions)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating meal suggestions: {str(e)}"
        )


@router.post(
    "/add",
    response_model=LoggedMeal,
    status_code=status.HTTP_201_CREATED,
    summary="Log a meal",
    description="Log a meal with its nutritional details for the current user."
)
async def log_meal(
        request: Request,
        meal_data: LogMealRequest,
        user=Depends(auth_guard)
) -> LoggedMeal:
    """Log a meal for the current user.

    Args:
        request: The incoming FastAPI request
        meal_data: Details of the meal to log
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        The logged meal with additional metadata

    Raises:
        HTTPException: If there is an error logging the meal
    """
    try:
        user_id = request.state.user["sub"]

        logged_meal = await meal_service.log_meal(user_id, meal_data)
        return logged_meal

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error logging meal: {str(e)}"
        )


@router.get(
    "/today",
    response_model=List[LoggedMeal],
    status_code=status.HTTP_200_OK,
    summary="Get today's meals",
    description="Retrieve all meals logged by the current user for today."
)
async def get_today_meals(
        request: Request,
        user=Depends(auth_guard)
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
        user_id = request.state.user["sub"]

        today_meals = await meal_service.get_meals_for_today(user_id)
        return today_meals

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving today's meals: {str(e)}"
        )


@router.get(
    "/progress/today",
    response_model=DailyProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Get daily progress",
    description="Calculate and return daily macro progress for the current user."
)
async def get_daily_progress(
        request: Request,
        user=Depends(auth_guard)
) -> DailyProgressResponse:
    """Calculate daily macro progress for the current user."""
    try:
        user_id = request.state.user["sub"]

        daily_progress = await meal_service.get_daily_progress(user_id)
        return daily_progress

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating daily progress: {str(e)}"
        )