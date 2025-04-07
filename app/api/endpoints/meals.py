"""API endpoints for meal suggestion functionality.

This module contains the FastAPI routes for the meal suggestion service.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse

from api.auth_guard import auth_guard
from models.meal import MealSuggestionRequest, MealSuggestionResponse

router = APIRouter()


@router.post(
    "/suggest-meals",
    response_model=MealSuggestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get meal suggestions based on macro requirements",
    description="Get personalized meal suggestions based on macro requirements. Returns a list of meal suggestions from restaurants in the specified location.",
)
async def suggest_meals(
        request: Request,
        meal_request: MealSuggestionRequest,
        user=Depends(auth_guard)
) -> MealSuggestionResponse:
    """Get personalized meal suggestions based on macro requirements.

    This endpoint takes the user's location and macro requirements and returns
    a list of meal suggestions from restaurants in the specified location.

    Args:
        request: The incoming FastAPI request
        meal_request: The meal suggestion request with location and macro targets
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        A response object containing a list of meal suggestions

    Raises:
        HTTPException: If there is an error processing the request
    """
    try:
        # You can access user information from the user parameter
        # For example: user_id = user.get("sub")
        user_id = request.state.user["sub"]
        print(user_id)
        meal_suggestions = await ai_service.get_meal_suggestions(meal_request)
        return MealSuggestionResponse(meals=meal_suggestions)

    except AIServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service error: {str(e)}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating meal suggestions: {str(e)}"
        )