"""API endpoints for meal logging and tracking functionality.

This module contains the FastAPI routes for logging meals and tracking daily progress.
"""

import logging
from fastapi import APIRouter, HTTPException, status, Depends, Request, Form, UploadFile, File
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
    MealSearchRequest,
    MealSearchResponse,
    MealType
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
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        The logged meal with additional metadata including meal_type

    Raises:
        HTTPException: If there is an error logging the meal
    """
    try:
        user_id = user.get("sub")

        # Validate photo if provided
        if photo:
            from app.utils.file_upload import validate_image_file
            validate_image_file(photo.filename, photo.content_type)

        # Create the meal request object
        from app.models.meal import LogMealRequest, LoggingMode, ServingUnitEnum
        from datetime import datetime
        
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
            meal_time=datetime.now(),
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
            period = period.replace(" ", "").upper()  # Normalize period input
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
        user_id = user.get("sub")

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
        user_id = user.get("sub")
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
    "/logs",
    response_model=List[LoggedMeal],
    status_code=status.HTTP_200_OK,
    summary="Get meal history for a date range",
    description="Retrieve meals logged by the current user for a specified date range or period.",
)
async def get_meal_history(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    period: Optional[str] = None,
    user=Depends(auth_guard),
) -> List[LoggedMeal]:
    """Retrieve meal history for a specified date range or period.

    Args:
        start_date: Start date for the meal history (optional if period is provided)
        end_date: End date for the meal history (optional, defaults to today)
        period: Predefined period (1W, 1M, 3M, 6M, 1Y, All) - overrides start_date
        user: The authenticated user

    Returns:
        A list of logged meals within the specified date range.

    Raises:
        HTTPException: If the request is invalid or an error occurs.
    """
    try:
        user_id = user.get("sub")

        if not end_date:
            end_date = date.today()

        if period:
            today = date.today()
            period = period.replace(" ", "").upper()  # Normalize period input
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

        meals = await meal_service.get_meals_by_date_range(
            user_id, start_date, end_date
        )
        return meals

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving meal history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving meal history: {str(e)}",
        )


@router.get(
    "/search",
    response_model=MealSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Search meal logs",
    description="Search for meals in user's logged meal history. Supports filtering by meal type, date range, and favorites.",
)
async def search_meals(
    query: str,
    meal_type: Optional[MealType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 20,
    favorites_only: Optional[bool] = None,
    user=Depends(auth_guard),
) -> MealSearchResponse:
    """Search for meals in user's logged meal history.

    Args:
        query: Search term for food item name
        meal_type: Filter by meal type (optional)
        start_date: Start date for search range (optional)
        end_date: End date for search range (optional)
        limit: Maximum number of results to return (1-100, default: 20)
        favorites_only: Filter to show only favorite meals (optional)
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        MealSearchResponse with matching logged meals

    Raises:
        HTTPException: If there is an error processing the search
    """
    try:
        user_id = user.get("sub")

        # Validate limit
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be between 1 and 100",
            )

        # Validate date range
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before or equal to end date",
            )

        # Create search request
        search_request = MealSearchRequest(
            query=query,
            meal_type=meal_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
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
    response_model=List[LoggedMeal],
    status_code=status.HTTP_200_OK,
    summary="Get favorite meals",
    description="Retrieve all meals marked as favorites by the current user.",
)
async def get_favorite_meals(
    limit: int = 50,
    user=Depends(auth_guard)
) -> List[LoggedMeal]:
    """Retrieve meals marked as favorites by the current user.

    Args:
        limit: Maximum number of results to return (1-100, default: 50)
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        List of favorite meals

    Raises:
        HTTPException: If there is an error retrieving favorite meals
    """
    try:
        user_id = user.get("sub")

        # Validate limit
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be between 1 and 100",
            )

        # Get favorite meals directly from meal service
        favorite_meals = await meal_service.get_favorite_meals(user_id, limit)
        
        return favorite_meals

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving favorite meals for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving favorite meals: {str(e)}",
        )
