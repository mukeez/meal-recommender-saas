"""API endpoints for meal suggestion functionality.

This module contains the FastAPI routes for the meal suggestion service.
"""
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from app.models.meal import MealSuggestionRequest, MealSuggestionResponse
from app.services.llm_service import ai_service, LLMServiceError

router = APIRouter()


@router.post(
    "/suggest-meals",
    response_model=MealSuggestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get meal suggestions based on macro requirements",
    response_description="List of suggested meals from restaurants",
)
async def suggest_meals(request: MealSuggestionRequest) -> MealSuggestionResponse:
    """Get personalized meal suggestions based on macro requirements.

    This endpoint takes the user's location and macro requirements and returns
    a list of meal suggestions from restaurants in the specified location.

    Args:
        request: The meal suggestion request with location and macro targets

    Returns:
        A response object containing a list of meal suggestions

    Raises:
        HTTPException: If there is an error processing the request
    """
    try:
        meal_suggestions = await ai_service.get_meal_suggestions(request)
        return MealSuggestionResponse(meals=meal_suggestions)

    except LLMServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI service error: {str(e)}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating meal suggestions: {str(e)}"
        )