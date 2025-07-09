"""Macro calculation endpoints for the meal recommendation API.

This module contains the FastAPI routes for calculating macronutrient requirements
with support for both metric and imperial unit systems.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth_guard import auth_guard

from app.models.macro_tracking import (
    MacroCalculatorRequest,
    MacroCalculatorResponse,
    MacroDistributionRequest,
    TimeToGoal,
    GoalType
)
from app.models.meal import CalculateMacrosRequest, CalculateMacrosResponse
from app.models.user import UpdateUserProfileRequest
from app.services.macros_service import macros_service, MacrosServiceError
from app.services.user_service import user_service
import traceback

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post(
    "/macros-setup",
    response_model=MacroCalculatorResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate daily macronutrient targets",
    description="Calculate daily calorie and macronutrient targets based on personal metrics and weight change goals. Supports both metric and imperial units.",
)
async def macros_setup_endpoint(
    request: MacroCalculatorRequest, user=Depends(auth_guard)
) -> MacroCalculatorResponse:
    """Calculate daily macronutrient targets with weight change projections."""
    try:
        user_id = user.get("sub")

        if request.manual_macros:
            response = MacroCalculatorResponse(**request.manual_macros.model_dump())
            # Save the manually entered macros to user preferences
            macros_service.save_user_preferences(user_id, response)
            return response
        
        target_weight = request.target_weight if request.target_weight else request.weight


        # Convert to metric if needed 
        weight_kg, height_cm, target_weight_kg, progress_rate_kg = macros_service.convert_to_metric(
            weight=request.weight, 
            height=request.height, 
            target_weight=target_weight,
            height_unit_preference=request.height_unit_preference,
            weight_unit_preference=request.weight_unit_preference,
            progress_rate=request.progress_rate
        )

        progress_rate_kg = -progress_rate_kg if request.goal_type == GoalType.LOSE else progress_rate_kg

        # Calculate BMR and TDEE
        bmr = macros_service.calculate_bmr(
            sex=request.sex, weight_kg=weight_kg, height_cm=height_cm, age=request.age
        )
        tdee = macros_service.calculate_tdee(bmr=bmr, activity_level=request.activity_level)

        # Adjust calories based on goal - now using kg/week for progress_rate
        goal_adjustment = macros_service.adjust_for_goal(
            tdee=tdee,
            goal_type=request.goal_type,
            progress_rate=progress_rate_kg, 
            sex=request.sex
        )

        # Calculate macros based on adjusted calories
        macro_response = macros_service.calculate_macros(
            weight_kg=weight_kg, calories=goal_adjustment["calories"]
        )

        dietary_preference = request.dietary_preference or "balanced"

        # Add the goal adjustment data to the response
        macro_response.progress_rate = abs(goal_adjustment["progress_rate"])
        macro_response.deficit_surplus = goal_adjustment["deficit_surplus"]
        macro_response.is_safe = goal_adjustment["is_safe"]
        macro_response.target_weight = target_weight_kg
        macro_response.goal_type = request.goal_type.value
        macro_response.dietary_preference = dietary_preference

        # Calculate time to goal if target weight is provided - using kg for all weights
        if target_weight_kg is not None and goal_adjustment["progress_rate"] != 0:
            time_calculation = macros_service.calculate_time_to_goal(
                current_weight=weight_kg,
                target_weight=target_weight_kg,
                progress_rate=goal_adjustment["progress_rate"]
            )
            macro_response.time_to_goal = TimeToGoal(**time_calculation)

        # Save the calculated macros
        macros_service.save_user_preferences(user_id, macro_response)

        user_data = {
            "age": request.age,
            "height": height_cm,
            "sex": request.sex,
            "has_macros": True,
            "height_unit_preference": request.height_unit_preference,
            "weight_unit_preference": request.weight_unit_preference,
        }


        if request.dob:
            user_data["dob"] = request.dob

        await user_service.update_user_profile(
            user_id=user_id,
            user_data=UpdateUserProfileRequest(**user_data)
        )

        return macro_response

    except MacrosServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error calculating macros: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating macros",
        )


@router.post(
    "/adjust-macros",
    response_model=MacroCalculatorResponse,
    status_code=status.HTTP_200_OK,
    summary="Adjust macronutrient distribution",
    description="Redistribute macronutrient targets while maintaining a fixed calorie target. Specify targets for one or two macros, and the remaining macro will be adjusted to maintain the calorie target.",
)
async def adjust_macro_distribution(
    request: MacroDistributionRequest, user=Depends(auth_guard)
) -> MacroCalculatorResponse:
    """Adjust the distribution of macronutrients while maintaining a fixed calorie target.

    This endpoint allows users to specify targets for one or two macronutrients,
    and the system will calculate the remaining macronutrient to maintain the
    given calorie target.

    Args:
        request: The macro adjustment request with fixed calorie target and macro preferences
        user: The authenticated user

    Returns:
        The adjusted macronutrient targets

    Raises:
        HTTPException: If the requested distribution is not possible or causes errors
    """
    try:
        user_id = user.get("sub")
        macro_response = macros_service.adjust_macro_distribution(
            protein=request.protein,
            carbs=request.carbs,
            fat=request.fat,
        )

        # Save the adjusted macros to user preferences
        macros_service.save_user_preferences(user_id, macro_response)

        return macro_response

    except MacrosServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adjusting macro distribution: {str(e)}",
        )


@router.post(
    "/calculate-macros",
    response_model=CalculateMacrosResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate macros based on amount changes",
    description="Calculate new macro values when the amount/quantity of a meal is changed. This is a stateless calculation endpoint for real-time macro updates.",
)
async def calculate_macros_endpoint(
    request: CalculateMacrosRequest, user=Depends(auth_guard)
) -> CalculateMacrosResponse:
    """Calculate new macro values based on amount changes.
    
    This endpoint performs a simple proportional calculation:
    new_macros = base_macros × (new_amount / base_amount)
    
    Args:
        request: The macro calculation request with base and new amounts
        user: The authenticated user
        
    Returns:
        Calculated macros rounded to 2 decimal places
        
    Raises:
        HTTPException: If amounts are invalid (zero or negative)
    """
    try:
        # Validate amounts
        if request.base_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Base amount must be greater than 0"
            )
        
        if request.new_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New amount must be greater than 0"
            )
        
        # Calculate the multiplier
        multiplier = request.new_amount / request.base_amount
        
        # Calculate new macros
        calculated_calories = round(request.base_calories * multiplier, 2)
        calculated_protein = round(request.base_protein * multiplier, 2)
        calculated_carbs = round(request.base_carbs * multiplier, 2)
        calculated_fat = round(request.base_fat * multiplier, 2)
        
        logger.info(f"Calculated macros for amount change: {request.base_amount} -> {request.new_amount} (multiplier: {multiplier})")
        
        return CalculateMacrosResponse(
            calories=calculated_calories,
            protein=calculated_protein,
            carbs=calculated_carbs,
            fat=calculated_fat
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating macros: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error calculating macros",
        )
