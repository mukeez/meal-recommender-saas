"""API endpoints for meal logging and tracking functionality.

This module contains the FastAPI routes for logging meals and tracking daily progress.
"""

import logging
from fastapi import APIRouter, HTTPException, status, Depends, Request, Form, UploadFile, File
from typing import List
from datetime import date, timedelta, datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.api.auth_guard import auth_guard
from app.models.meal import (
    LogMealRequest,
    LoggedMeal,
    LoggingMode,
    ServingUnitEnum,
    MealFeedbackRequest,
    MealSuggestionRequest,
    MealSuggestionResponse,
    DailyProgressResponse,
    ProgressSummary,
    UpdateMealRequest,
    UpdateMealResponse,
    DeleteMealResponse,
    MealSearchRequest,
    MealSearchResponse,
    MealType,
    MacroSummary,
    PaginatedMealSearchRequest,
    PaginatedMealSearchResponse,
    PaginatedMealLogsResponse,
    PaginatedFavoriteMealsResponse,
    RecipeSuggestionRequest,
    RecipeSuggestionResponse,
)


from app.services.meal_service import meal_service
from app.services.meal_llm_service import meal_llm_service
from app.services.recipe_llm_service import recipe_llm_service
from app.services.restaurant_service import restaurant_service
from app.services.google_places_service import google_places_service, GooglePlacesAPIError
from app.services.cache_service import cache_service
from app.services.restaurant_meal_matching_service import restaurant_meal_matching_service
from app.services.user_service import user_service
from app.utils.file_upload import validate_image_file


import traceback
import asyncio


router = APIRouter()

logger = logging.getLogger(__name__)

# Minimum match score threshold
MIN_MATCH_SCORE = 50


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
        user_id = user.get("id")
        user_email = user.get("email")

        meal_suggestions = await meal_llm_service(
            request=meal_request, user_id=user_email, restaurants=[]
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
    description="Log a meal with its nutritional details for the current user. Meal type is automatically classified based on time of day. Optionally upload a photo of the meal.",
)
async def log_meal(
    name: str = Form(..., description="Name of the meal"),
    description: Optional[str] = Form(None, description="Description of the meal"),
    protein: float = Form(..., description="Protein amount in grams", ge=0),
    carbs: float = Form(..., description="Carbohydrate amount in grams", ge=0),
    fat: float = Form(..., description="Fat amount in grams", ge=0),
    calories: float = Form(..., description="Total calories", ge=0),
    notes: Optional[str] = Form(None, description="Additional notes about the meal"),
    logging_mode: str = Form("manual", description="How the meal was logged (manual, barcode, scanned)"),
    serving_unit: str = Form("grams", description="Unit of measurement for serving"),
    amount: float = Form(1.0, description="Amount/quantity of the serving unit", ge=0),
    favorite: bool = Form(False, description="Whether to mark this meal as a favorite"),
    photo: Optional[UploadFile] = File(None, description="Meal photo (optional)"),
    meal_time: Optional[datetime] = Form(None, description="Time of the meal (optional, defaults to current time)"),
    user=Depends(auth_guard)
) -> LoggedMeal:
    """Log a meal for the current user with automatic meal type classification.

    Args:
        name: Name of the meal
        description: Description of the meal (optional)
        protein: Protein amount in grams
        carbs: Carbohydrate amount in grams
        fat: Fat amount in grams
        calories: Total calories
        notes: Additional notes about the meal (optional)
        logging_mode: How the meal was logged
        serving_unit: Unit of measurement for serving
        amount: Amount/quantity of the serving unit
        favorite: Whether to mark this meal as a favorite
        photo: Meal photo file (optional)
        meal_time: Time of the meal (optional, defaults to current time)
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        The logged meal with additional metadata including meal_type

    Raises:
        HTTPException: If there is an error logging the meal
    """
    try:
        user_id = user.get("id")

        # Set meal_time to current time if not provided
        if meal_time is None:
            meal_time = datetime.now()

        # Validate photo if provided
        if photo:
            validate_image_file(photo.filename, photo.content_type)

        
        # Force serving_unit to "grams" for scanned/barcode meals
        final_serving_unit = serving_unit
        if logging_mode in ["barcode", "scanned"]:
            final_serving_unit = "grams"
        
        meal_data = LogMealRequest(
            name=name,
            description=description,
            protein=protein,
            carbs=carbs,
            fat=fat,
            calories=calories,
            meal_time=meal_time,
            meal_type=None,  # Will be auto-classified
            notes=notes,
            logging_mode=LoggingMode(logging_mode),
            serving_unit=ServingUnitEnum(final_serving_unit),
            amount=amount,
            favorite=favorite
        )

        # Log the meal first
        logged_meal = await meal_service.log_meal(user_id, meal_data)

        # Upload photo if provided
        if photo:
            try:
                file_content = await photo.read()
                photo_url = await meal_service.upload_meal_photo(
                    user_id=user_id,
                    meal_id=logged_meal.id,
                    file_content=file_content,
                    content_type=photo.content_type or "image/jpeg"
                )
                
                # Update the meal in the database with the photo URL
                await meal_service.update_meal_photo_url(user_id, logged_meal.id, photo_url)
                
                # Update the response object with the photo URL
                logged_meal.photo_url = photo_url
                
            except Exception as e:
                logger.warning(f"Failed to upload meal photo for meal {logged_meal.id}: {str(e)}")
                # Continue without photo if upload fails
            finally:
                await photo.close()
        
        from app.utils.helper_functions import trigger_macro_goal_completion_notification

        await trigger_macro_goal_completion_notification(user_id)
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
        user_id = user.get("id")

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
        user_id = user.get("id")
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
    period: Optional[str] = None,
    user=Depends(auth_guard),
) -> ProgressSummary:
    """Retrieve macro intake progress data with intelligent aggregation by period.

    Args:
        period: Time period for aggregation:
            - 1w: Current week by weekdays (Mon, Tue, Wed, Thu, Fri, Sat, Sun)  
            - 1m: Current month by weeks (W1, W2, W3, W4, W5)
            - 3m: Last 3 complete months by abbreviated month names (Oct, Nov, Dec)
            - 6m: Last 6 complete months by abbreviated month names (Jul, Aug, Sep, Oct, Nov, Dec)
            - 1y: Current calendar year by abbreviated month names (Jan, Feb, Mar, etc.)
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        Progress summary with period-based aggregation, averages, and comparison to goals

    Raises:
        HTTPException: If there is an error retrieving the progress data
    """
    try:
        user_id = user.get("id")

        # Set default period if none provided
        if not period:
            period = "1w"  # Default to 1 week

        progress_summary = await meal_service.get_progress_summary(
            user_id, period
        )
        return progress_summary

    except HTTPException:
        traceback.print_exc()
        raise
    except Exception as e:
        logger.error(f"Error retrieving progress data: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving progress data: {str(e)}",
        )


@router.put(
    "/{meal_id}",
    response_model=UpdateMealResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a meal",
    description="Update an existing logged meal for the current user. Optionally upload a new photo.",
)
async def update_meal(
    meal_id: str,
    name: Optional[str] = Form(None, description="Name of the meal"),
    description: Optional[str] = Form(None, description="Description of the meal"),
    protein: Optional[float] = Form(None, description="Protein amount in grams", ge=0),
    carbs: Optional[float] = Form(None, description="Carbohydrate amount in grams", ge=0),
    fat: Optional[float] = Form(None, description="Fat amount in grams", ge=0),
    calories: Optional[float] = Form(None, description="Total calories", ge=0),
    notes: Optional[str] = Form(None, description="Additional notes about the meal"),
    logging_mode: Optional[str] = Form(None, description="How the meal was logged (manual, barcode, scanned)"),
    serving_unit: Optional[str] = Form(None, description="Unit of measurement for serving"),
    amount: Optional[float] = Form(None, description="Amount/quantity of the serving unit", ge=0),
    favorite: Optional[bool] = Form(None, description="Whether to mark this meal as a favorite"),
    photo: Optional[UploadFile] = File(None, description="New meal photo (optional)"),
    meal_time: Optional[datetime] = Form(None, description="Time of the meal (optional)"),
    user=Depends(auth_guard),
) -> UpdateMealResponse:
    """Update an existing logged meal for the current user.

    Args:
        meal_id: ID of the meal to update
        name: Name of the meal (optional)
        description: Description of the meal (optional)
        protein: Protein amount in grams (optional)
        carbs: Carbohydrate amount in grams (optional)
        fat: Fat amount in grams (optional)
        calories: Total calories (optional)
        notes: Additional notes about the meal (optional)
        logging_mode: How the meal was logged (optional)
        serving_unit: Unit of measurement for serving (optional)
        amount: Amount/quantity of the serving unit (optional)
        favorite: Whether to mark this meal as a favorite (optional)
        photo: New meal photo file (optional)
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        UpdateMealResponse with success message and updated meal data

    Raises:
        HTTPException: If there is an error updating the meal
    """
    try:
        user_id = user.get("id")

        # Validate photo if provided
        if photo:
            from app.utils.file_upload import validate_image_file
            validate_image_file(photo.filename, photo.content_type)

        # Create the meal update request object
        from app.models.meal import UpdateMealRequest, LoggingMode, ServingUnitEnum
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if protein is not None:
            update_data["protein"] = protein
        if carbs is not None:
            update_data["carbs"] = carbs
        if fat is not None:
            update_data["fat"] = fat
        if calories is not None:
            update_data["calories"] = calories
        if notes is not None:
            update_data["notes"] = notes
        if logging_mode is not None:
            update_data["logging_mode"] = LoggingMode(logging_mode)
        if serving_unit is not None:
            # Force serving_unit to "grams" for scanned/barcode meals
            final_serving_unit = serving_unit
            if logging_mode in ["barcode", "scanned"]:
                final_serving_unit = "grams"
            update_data["serving_unit"] = ServingUnitEnum(final_serving_unit)
        if amount is not None:
            update_data["amount"] = amount
        if favorite is not None:
            update_data["favorite"] = favorite
        if meal_time is not None:
            update_data["meal_time"] = meal_time

        meal_data = UpdateMealRequest(**update_data)

        # Update the meal
        updated_meal = await meal_service.update_meal(user_id, meal_id, meal_data)

        # Upload photo if provided
        if photo:
            try:
                file_content = await photo.read()
                photo_url = await meal_service.upload_meal_photo(
                    user_id=user_id,
                    meal_id=meal_id,
                    file_content=file_content,
                    content_type=photo.content_type or "image/jpeg"
                )
                
                # Update the meal in the database with the photo URL
                await meal_service.update_meal_photo_url(user_id, meal_id, photo_url)
                
                # Update the response object with the photo URL
                updated_meal.photo_url = photo_url
                
            except Exception as e:
                logger.warning(f"Failed to upload meal photo for meal {meal_id}: {str(e)}")
                # Continue without photo if upload fails
            finally:
                await photo.close()

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
    """Delete a logged meal.

    Args:
        meal_id: ID of the meal to delete
        user: The authenticated user

    Returns:
        A response confirming the deletion

    Raises:
        HTTPException: If the meal is not found or cannot be deleted
    """
    try:
        user_id = user.get("id")
        deleted_meal_id = await meal_service.delete_meal(user_id, meal_id)
        return DeleteMealResponse(
            message="Meal deleted successfully", meal_id=deleted_meal_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting meal {meal_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting meal: {str(e)}",
        )


@router.get(
    "/search",
    response_model=PaginatedMealSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search meal logs with pagination",
    description="Search for meals in user's logged meal history with pagination support. Supports filtering by meal type, date range, and favorites.",
)
async def search_meals(
    query: str,
    meal_type: Optional[MealType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
    favorites_only: Optional[bool] = None,
    user=Depends(auth_guard),
) -> PaginatedMealSearchResponse:
    """Search for meals in user's logged meal history with pagination.

    Args:
        query: Search term for food item name
        meal_type: Filter by meal type (optional)
        start_date: Start date for search range (optional)
        end_date: End date for search range (optional)
        page: Page number (1-based, default: 1)
        page_size: Number of items per page (default: 20)
        favorites_only: Filter to show only favorite meals (optional)
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        PaginatedMealSearchResponse with matching logged meals and pagination info

    Raises:
        HTTPException: If there is an error processing the search
    """
    try:
        user_id = user.get("id")

        # Validate pagination parameters
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page must be 1 or greater",
            )
        
        if page_size < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page size must be 1 or greater",
            )

        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before or equal to end date",
            )

        # Create paginated search request
        search_request = PaginatedMealSearchRequest(
            query=query,
            meal_type=meal_type,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size,
            favorites_only=favorites_only
        )

        # Perform the search
        search_results = await meal_service.search_meals(user_id, search_request)
        
        return search_results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching meals for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching meals: {str(e)}",
        )


@router.get(
    "/favorites",
    response_model=PaginatedFavoriteMealsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get paginated favorite meals",
    description="Retrieve meals marked as favorites by the current user with pagination support.",
)
async def get_favorite_meals(
    page: int = 1,
    page_size: int = 20,
    user=Depends(auth_guard)
) -> PaginatedFavoriteMealsResponse:
    """Retrieve paginated meals marked as favorites by the current user.

    Args:
        page: Page number (1-based, default: 1)
        page_size: Number of items per page (default: 20)
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        PaginatedFavoriteMealsResponse with favorite meals and pagination info

    Raises:
        HTTPException: If there is an error retrieving favorite meals
    """
    try:
        user_id = user.get("id")

        # Validate pagination parameters
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page must be 1 or greater",
            )
        
        if page_size < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page size must be 1 or greater",
            )

        # Get favorite meals
        paginated_favorites = await meal_service.get_favorite_meals(user_id, page, page_size)
        
        return paginated_favorites

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving paginated favorite meals for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving favorite meals: {str(e)}",
        )


@router.get(
    "/logs",
    response_model=PaginatedMealLogsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get paginated meal history for a date range",
    description="Retrieve meals logged by the current user for a specified date range or period with pagination support.",
)
async def get_meal_history(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    period: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user=Depends(auth_guard),
) -> PaginatedMealLogsResponse:
    """Retrieve paginated meal history for a specified date range or period.

    Args:
        start_date: Start date for the meal history (optional if period is provided)
        end_date: End date for the meal history (optional, defaults to today)
        period: Predefined period (1W, 1M, 3M, 6M, 1Y, All) - overrides start_date
        page: Page number (1-based, default: 1)
        page_size: Number of items per page (default: 20)
        user: The authenticated user

    Returns:
        PaginatedMealLogsResponse with meals and pagination information

    Raises:
        HTTPException: If the request is invalid or an error occurs.
    """
    try:
        user_id = user.get("id")

        # Validate pagination parameters
        if page < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page must be 1 or greater",
            )
        
        if page_size < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Page size must be 1 or greater",
            )

        if not end_date:
            end_date = date.today()

        if period:
            today = date.today()
            period = period.replace(" ", "").lower()  # Normalize period input
            if period == "1w":
                start_date = today - timedelta(days=7)
            elif period == "1m":
                start_date = today - timedelta(days=30)
            elif period == "3m":
                start_date = today - timedelta(days=90)
            elif period == "6m":
                start_date = today - timedelta(days=180)
            elif period == "1y":
                start_date = today - timedelta(days=365)
            elif period == "all":
                start_date = await meal_service.get_first_meal_date(user_id)
                if not start_date:
                    start_date = today - timedelta(days=30)  # Default if no meals
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid period parameter: {period}",
                )

        if not start_date:
            start_date = end_date

        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before or equal to end date",
            )

        paginated_meals = await meal_service.get_meals_by_date_range(
            user_id, start_date, end_date, page, page_size
        )
        return paginated_meals

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving paginated meal history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving meal history: {str(e)}",
        )


@router.post(
    "/suggest-recipes",
    response_model=RecipeSuggestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get recipe suggestions based on macro requirements",
    description="Get personalized recipe suggestions based on macro requirements. Returns a list of recipe suggestions.",
)
async def suggest_recipes(
    recipe_request: RecipeSuggestionRequest, user=Depends(auth_guard)
) -> RecipeSuggestionResponse:
    """Get personalized recipe suggestions based on macro requirements.

    This endpoint takes the user's macro requirements and returns
    a list of recipe suggestions.

    Args:
        recipe_request: The recipe suggestion request with macro targets
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        A response object containing a list of recipe suggestions

    Raises:
        HTTPException: If there is an error processing the request
    """
    try:
        # Extract user ID from the authenticated user
        user_id = user.get("id")
        user_email = user.get("email")

        recipe_suggestions = await recipe_llm_service(
            request=recipe_request, user_id=user_email
        ).get_recipe_suggestions()
        return recipe_suggestions

    except Exception as e:
        logger.error(f"Error generating recipe suggestions for user:{user_id}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating recipe suggestions",
        )


@router.post(
    "/feedback",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Submit meal feedback",
    description="Submit feedback for a specific meal.",
)
async def log_meal_feedback(feedback: MealFeedbackRequest, user=Depends(auth_guard)):
    """Log feedback for a specific meal.

    Args:
        payload: The feedback payload containing meal name and feedback type
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        A response object indicating the result of the feedback logging

    Raises:
        HTTPException: If there is an error processing the request
    """
    try:
        user_id = user.get("id")

        feedback_data = feedback.model_dump()
        feedback_data["user_id"] = user_id

        await meal_service.log_feedback(feedback_data)
        return {"message": "Feedback submitted successfully"}
    except Exception as e:
        logger.error(f"Error logging meal feedback for user:{user_id}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error logging meal feedback",
        )


@router.get(
    "/map-pins",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get restaurant map pins with meal recommendations",
    description="Returns nearby restaurants as map pins with top meal recommendations. Uses Google Places API with caching. User preferences (macros, dietary restrictions) are automatically fetched from user profile.",
)
async def get_map_pins(
    latitude: float,
    longitude: float,
    radius_km: float = 5.0,
    query: Optional[str] = None,
    limit: int = 10,
    user=Depends(auth_guard)
):
    """Get nearby restaurants as map pins with meal recommendations.
    
    This endpoint:
    1. Fetches user's macro goals and dietary preferences from profile
    2. Checks Redis cache first (24h TTL)
    3. Queries Google Places Nearby Search
    4. Gets place details for each restaurant
    5. Generates meal recommendations using LLM based on user's preferences
    6. Filters out restaurants with match score < 50%
    7. Caches the response
    
    Args:
        latitude: Latitude coordinate (-90 to 90)
        longitude: Longitude coordinate (-180 to 180)
        radius_km: Search radius in kilometers (0.1 to 50, default: 5.0)
        query: Search query (cuisine type, restaurant name)
        limit: Maximum number of results (1-200, default: 50)
        user: Authenticated user
        
    Returns:
        MapPinsResponse with restaurant pins based on user's preferences
        
    Raises:
        HTTPException: On validation or processing errors
    """
    try:
        user_id = user.get("id")
        user_email = user.get("email")
        
        # Validate parameters
        if not (-90 <= latitude <= 90):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Latitude must be between -90 and 90"
            )
        
        if not (-180 <= longitude <= 180):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Longitude must be between -180 and 180"
            )
        
        if not (0.1 <= radius_km <= 50):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Radius must be between 0.1 and 50 km"
            )
        
        if not (1 <= limit <= 200):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be between 1 and 200"
            )
        
        # Fetch user preferences (macro goals and dietary restrictions)
        logger.info(f"Fetching preferences for user {user_id}")
        user_prefs = await user_service.get_user_preferences(user_id)
        
        # Extract dietary restrictions and preferences
        dietary_restrictions_list = user_prefs.get("dietary_restrictions", [])
        dietary_preference = user_prefs.get("dietary_preference")
        
        # Extract macro targets from user's macro goals
        macro_targets = {}
        macro_goals = user_prefs.get("macro_goals", {})
        if macro_goals:
            if macro_goals.get("calories"):
                macro_targets["calories"] = macro_goals.get("calories")
            if macro_goals.get("protein"):
                macro_targets["protein"] = macro_goals.get("protein")
            if macro_goals.get("carbs"):
                macro_targets["carbs"] = macro_goals.get("carbs")
            if macro_goals.get("fat"):
                macro_targets["fat"] = macro_goals.get("fat")
        
        logger.info(f"User preferences - Macro targets: {macro_targets}, Dietary restrictions: {dietary_restrictions_list}")
        
        # Prepare filter dict for caching (include user preferences)
        filters = {
            "query": query,
            "calories": macro_targets.get("calories"),
            "protein": macro_targets.get("protein"),
            "carbs": macro_targets.get("carbs"),
            "fat": macro_targets.get("fat"),
            "dietary_restrictions": dietary_restrictions_list,
            "dietary_preference": dietary_preference,
            "limit": limit,
            "user_id": user_id  # Include user_id for per-user caching
        }
        
        # Check cache
        cache_key = cache_service.generate_cache_key(latitude, longitude, radius_km, filters)
        cached_response = await cache_service.get_cached_map_pins(cache_key)
        
        if cached_response:
            logger.info(f"Returning cached map pins for user {user_id}")
            cached_response["cached"] = True
            return cached_response
        
        logger.info(f"Searching Google Places: lat={latitude}, lng={longitude}, radius={radius_km}km")
        
        # Query Google Places
        try:
            places = await google_places_service.nearby_search(
                latitude=latitude,
                longitude=longitude,
                radius=int(radius_km * 1000),  # Convert km to meters
                keyword=query,
                place_type="restaurant"
            )
        except GooglePlacesAPIError as e:
            logger.error(f"Google Places API error: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Location service temporarily unavailable"
            )
        
        if not places:
            # Return empty response
            empty_response = {
                "pins": [],
                "total_count": 0,
                "search_center": {"lat": latitude, "lng": longitude},
                "search_radius_km": radius_km,
                "filters_applied": filters,
                "cached": False
            }
            return empty_response
        
        # Limit results
        places = places[:limit]
        
        logger.info(f"Processing {len(places)} restaurants")
        
        # Process restaurants in parallel
        async def process_restaurant(place):
            try:
                place_id = place.get("place_id")
                
                # Get place details
                details = await google_places_service.get_place_details(place_id)
                
                # Extract menu URL
                menu_url = google_places_service.extract_menu_url(details)
                
                # Prepare restaurant data
                geometry = details.get("geometry", {}).get("location", {})
                restaurant_data = {
                    "google_place_id": place_id,
                    "name": details.get("name", "Unknown"),
                    "latitude": geometry.get("lat"),
                    "longitude": geometry.get("lng"),
                    "address": details.get("formatted_address", ""),
                    "rating": details.get("rating"),
                    "price_level": details.get("price_level"),
                    "place_types": details.get("types", []),
                    "website": details.get("website"),
                    "phone": details.get("formatted_phone_number"),
                    "menu_url": menu_url,
                    "photo_references": [photo.get("photo_reference") for photo in details.get("photos", [])[:3]]
                }
                
                # Generate meal recommendation using LLM with user's preferences
                user_prefs_with_id = {
                    "user_id": user_email,
                    "dietary_restrictions": dietary_restrictions_list,
                    "dietary_preference": dietary_preference
                }
                
                meal = await restaurant_meal_matching_service.get_top_meal_for_restaurant(
                    restaurant=restaurant_data,
                    user_preferences=user_prefs_with_id,
                    macro_targets=macro_targets if macro_targets else None
                )
                
                # Check match score threshold
                match_score = meal.get("match_score", 0)
                
                if match_score < MIN_MATCH_SCORE:
                    logger.info(f"Filtering out {restaurant_data['name']} (match score: {match_score})")
                    return None
                
                # Build restaurant pin
                # Calculate distance (simple haversine)
                from math import radians, cos, sin, asin, sqrt
                
                lat1, lon1 = radians(latitude), radians(longitude)
                lat2, lon2 = radians(restaurant_data["latitude"]), radians(restaurant_data["longitude"])
                
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * asin(sqrt(a))
                distance_km = 6371 * c  # Earth radius in km
                
                # Extract cuisine types (LLM infers from place_types)
                cuisine_types_extracted = []
                for place_type in restaurant_data["place_types"]:
                    if "_restaurant" in place_type:
                        cuisine = place_type.replace("_restaurant", "").replace("_", " ").title()
                        cuisine_types_extracted.append(cuisine)
                
                pin = {
                    "id": place_id,  # Use Google Place ID as temporary ID
                    "google_place_id": place_id,
                    "name": restaurant_data["name"],
                    "latitude": restaurant_data["latitude"],
                    "longitude": restaurant_data["longitude"],
                    "address": restaurant_data["address"],
                    "top_meal": {
                        "name": meal.get("name"),
                        "match_score": match_score,
                        "macros": meal.get("macros"),
                        "description": meal.get("description"),
                        "estimated": meal.get("estimated", True)
                    },
                    "rating": restaurant_data["rating"],
                    "price_level": restaurant_data["price_level"],
                    "distance_km": round(distance_km, 2),
                    "cuisine_types": cuisine_types_extracted,
                    "photo_url": None,  # For future use
                    "menu_url": menu_url
                }
                
                logger.info(f"Processed: {restaurant_data['name']} (match: {match_score}%)")
                
                return pin
                
            except Exception as e:
                logger.error(f"Error processing restaurant: {e}")
                return None
        
        # Process all restaurants in parallel
        tasks = [process_restaurant(place) for place in places]
        pins = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out None and exceptions
        valid_pins = [pin for pin in pins if pin is not None and not isinstance(pin, Exception)]
        
        logger.info(f"Generated {len(valid_pins)} pins with match score >= {MIN_MATCH_SCORE}%")
        
        # Build response
        response = {
            "pins": valid_pins,
            "total_count": len(valid_pins),
            "search_center": {"lat": latitude, "lng": longitude},
            "search_radius_km": radius_km,
            "filters_applied": {
                "query": query,
                "macro_targets": macro_targets,
                "dietary_restrictions": dietary_restrictions_list,
                "dietary_preference": dietary_preference,
                "limit": limit
            },
            "cached": False
        }
        
        # Cache response
        await cache_service.set_cached_map_pins(cache_key, response)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in map pins endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error loading restaurant map data"
        )
