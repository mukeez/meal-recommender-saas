"""User endpoints for the meal recommendation API.

This module contains FastAPI routes for user-related functionality.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Form,
    UploadFile,
    File,
    Request,
)
from datetime import datetime
import logging
import httpx

from app.api.auth_guard import auth_guard
from app.core.config import settings
from app.models.user import (
    UpdateUserPreferencesRequest,
    UserPreferences,
    UpdateUserProfileRequest,
    UserProfile,
    Sex,
    HeightUnitPreference,
    WeightUnitPreference,
)
from app.services.user_service import user_service
from app.services.stripe_service import stripe_service, StripeServiceError
from app.services.mail_service import mail_service
from typing import Optional
import traceback

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/me",
    summary="Get current user profile",
    description="Retrieve the profile of the currently authenticated user.",
    response_model=UserProfile,
)
async def get_user_profile(user=Depends(auth_guard)) -> UserProfile:
    """Get the current user's profile.

    This is a protected endpoint that requires authentication.

    Args:
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        The user profile information
    """
    try:
        profile = await user_service.get_user_profile(user_id=user.get("sub"))
        return profile
    except HTTPException:
        # re-raise httpexceptions without modification
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve user profile with error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user profile")


@router.patch(
    "/me",
    summary="Update current user profile",
    description="Update the profile of the currently authenticated user.",
    response_model=UserProfile,
)
async def update_user_profile(
    request: Request,
    display_name: Optional[str] = Form(
        None, description="new user display name (optional)"
    ),
    first_name: Optional[str] = Form(
        None, description="new user first name (optional)"
    ),
    last_name: Optional[str] = Form(None, description="new user last name (optional)"),
    age: Optional[int] = Form(None, description="new user age (optional)"),
    dob: Optional[str] = Form(None, description="new date of birth (YYYY-MM-DD) (optional)"),
    sex: Optional[str] = Form(None, description="new biological sex (male/female) (optional)"),
    height: Optional[float] = Form(None, description="new height (optional)"),
    weight: Optional[float] = Form(None, description="new weight (optional)"),
    height_unit_preference: Optional[str] = Form(None, description="height unit preference (metric/imperial) (optional)"),
    weight_unit_preference: Optional[str] = Form(None, description="weight unit preference (metric/imperial) (optional)"),
    avatar: Optional[UploadFile] = File(None, description="new avatar image(optional)"),
    meal_reminder_preferences_set: Optional[bool] = Form(
        False, description="Whether the user has meal reminder preferences set"
    ),
    user=Depends(auth_guard),
):
    """Update the current user's profile.

    This is a protected endpoint that requires authentication.

    Args:
        user: The authenticated user (injected by the auth_guard dependency)
        display_name: new user display name (optional)
        first_name: new user first name (optional)
        last_name: new user last name (optional)
        age: new user age (optional)
        dob: new date of birth in YYYY-MM-DD format (optional)
        sex: new biological sex (male/female) (optional)
        height: new height value (optional)
        weight: new weight value (optional)
        height_unit_preference: height unit preference (metric/imperial) (optional)
        weight_unit_preference: weight unit preference (metric/imperial) (optional)
        avatar: new avatar image (optional)
        meal_reminder_preferences_set: Whether the user has meal reminder preferences set

    Returns:
        The user profile information
    """
    try:
        user_id = user.get("sub")
        
        # Convert string values to enums where applicable
        sex_enum = Sex(sex) if sex else None
        height_unit_enum = HeightUnitPreference(height_unit_preference) if height_unit_preference else None
        weight_unit_enum = WeightUnitPreference(weight_unit_preference) if weight_unit_preference else None
        
        if avatar:
            if not avatar.content_type or not avatar.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Only image files allowed.")
            file_content = await avatar.read()
            content_type = avatar.content_type or "image/jpeg"
            avatar_url = await user_service.upload_user_avatar(
                user_id=user_id, file_content=file_content, content_type=content_type
            )
            await avatar.close()
            user_data = UpdateUserProfileRequest(
                display_name=display_name,
                first_name=first_name,
                last_name=last_name,
                avatar_url=avatar_url,
                meal_reminder_preferences_set=meal_reminder_preferences_set,
                age=age,
                dob=dob,
                sex=sex_enum,
                height=height,
                weight=weight,
                height_unit_preference=height_unit_enum,
                weight_unit_preference=weight_unit_enum,
            )
        else:
            user_data = UpdateUserProfileRequest(
                display_name=display_name,
                first_name=first_name,
                last_name=last_name,
                meal_reminder_preferences_set=meal_reminder_preferences_set,
                age=age,
                dob=dob,
                sex=sex_enum,
                height=height,
                weight=weight,
                avatar_url=None,
                height_unit_preference=height_unit_enum,
                weight_unit_preference=weight_unit_enum,
            )
        profile = await user_service.update_user_profile(
            user_id=user_id, user_data=user_data
        )
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update user profile with error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user profile")


@router.patch(
    "/me/fcm-token",
    summary="Update FCM token",
    description="Update the FCM token for push notifications.",
)
async def update_fcm_token(
    body: dict,
    user=Depends(auth_guard),
):
    """Update the FCM token for the current user.

    This is a protected endpoint that requires authentication.

    Args:
        body: Dict containing the new FCM token (expects {"fcm_token": ...})
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        A success message indicating the token was updated
    """
    try:
        fcm_token = body.get("fcm_token")
        if not fcm_token:
            raise HTTPException(status_code=400, detail="FCM token is required")
        user_id = user.get("sub")
        await user_service.update_fcm_token(user_id=user_id, fcm_token=fcm_token)
        return {"message": "FCM token updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update FCM token with error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update FCM token")


@router.get(
    "/preferences",
    response_model=UserPreferences,
    status_code=status.HTTP_200_OK,
    summary="Get user preferences",
    description="Retrieve the current user's dietary preferences and macro targets.",
)
async def get_user_preferences(user=Depends(auth_guard)):
    """
    Retrieve the current user's preferences.

    Args:
        user: Authenticated user from auth_guard

    Returns:
        UserPreferences object with current preferences
    """
    try:
        user_id = user.get("sub")

        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service configuration error"
            )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.SUPABASE_URL}/rest/v1/user_preferences",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                    "Content-Type": "application/json",
                },
                params={"user_id": "eq." + user_id},
            )

            if response.status_code != 200:
                logger.error(f"Failed to fetch preferences for user {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User preferences not found",
                )

            preferences_data = response.json()

            if not preferences_data:
                logger.warning(f"No preferences found for user {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User preferences not found",
                )

            return UserPreferences(**preferences_data[0])

    except Exception as e:
        logger.error(f"Error retrieving user preferences: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving preferences: {str(e)}",
        )


@router.patch(
    "/preferences",
    response_model=UserPreferences,
    status_code=status.HTTP_200_OK,
    summary="Update user preferences",
    description="Update the current user's dietary preferences, macro targets",
)
async def update_user_preferences(
    preferences_update: UpdateUserPreferencesRequest, user=Depends(auth_guard)
):
    """
    Update the current user's preferences.

    Args:
        preferences_update: Partial update to user preferences including dietary preferences,
                           macro targets, and unit preferences (kg/lbs)
        user: Authenticated user from auth_guard

    Returns:
        Updated UserPreferences object
    """
    try:
        user_id = user.get("sub")

        update_data = {
            k: v
            for k, v in preferences_update.model_dump(exclude_unset=True).items()
            if v is not None
        }

        update_data["updated_at"] = datetime.now().isoformat()

        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service configuration error"
            )
       
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{settings.SUPABASE_URL}/rest/v1/user_preferences",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
                params={"user_id": "eq." + user_id},
                json=update_data,
            )

            if response.status_code not in (200, 201):
                logger.error(f"Failed to update preferences for user {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update user preferences",
                )

            updated_preferences = response.json()

            if not updated_preferences:
                logger.warning(f"No preferences found for user {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User preferences not found",
                )

            return UserPreferences(**updated_preferences[0])

    except Exception as e:
        logger.error(f"Error updating user preferences: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating preferences: {str(e)}",
        )


@router.delete(
    "/me",
    summary="Delete user account and all data",
    description="Permanently delete the user account, cancel all subscriptions, and remove all associated data. This action cannot be undone.",
    status_code=status.HTTP_200_OK,
)
async def delete_user_account(user=Depends(auth_guard)) -> dict:
    """Delete the current user's account and all associated data.

    This endpoint will:
    1. Cancel all active Stripe subscriptions
    2. Delete all user data from the database (profile, preferences, meals, etc.)
    3. Send a confirmation email
    4. Log the deletion for audit purposes

    WARNING: This action is irreversible and will permanently delete all user data.

    Args:
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        A confirmation message

    Raises:
        HTTPException: If the deletion process fails
    """
    try:
        user_id = user.get("sub")
        
        logger.info(f"Account deletion requested for user: {user_id}")
        
        
        try:
            user_profile = await user_service.get_user_profile(user_id)
            user_email = user_profile.email
        except Exception as e:
            logger.warning(f"Could not retrieve user profile during deletion: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve user profile. Please contact support."
            )
            
        # Cancel all active Stripe subscriptions
        subscription_cancelled = False
        try:
            has_active_subscription = await stripe_service.has_active_subscription(user_id)
            if has_active_subscription:
                logger.info(f"Cancelling active subscription for user: {user_id}")
                await stripe_service.cancel_user_subscription(
                    user_id=user_id, 
                    cancel_at_period_end=False  # Cancel immediately for account deletion
                )
                subscription_cancelled = True
                logger.info(f"Successfully cancelled subscription for user: {user_id}")
            else:
                logger.info(f"No active subscription found for user: {user_id}")
        except StripeServiceError as e:
            logger.error(f"Failed to cancel subscription for user {user_id}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Unexpected error cancelling subscription for user {user_id}: {str(e)}")
            
        # Delete all user data from database
        try:
            await user_service.delete_user_account(user_id)
            logger.info(f"Successfully deleted all data for user: {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete user data for user {user_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user data. Please contact support."
            )
            
        # Send confirmation email
        try:
            await mail_service.send_email(
                recipient=user_email,
                subject="Account Deletion Confirmation - Macro Meals",
                template_name="account_deleted.html",
                context={
                    "user_email": user_email,
                    "deletion_date": datetime.now().strftime("%B %d, %Y"),
                    "subscription_cancelled": subscription_cancelled
                }
            )
            logger.info(f"Sent account deletion confirmation email to: {user_email}")
        except Exception as e:
            logger.warning(f"Failed to send deletion confirmation email to {user_email}: {str(e)}")
                
        logger.info(f"Account deletion completed successfully for user: {user_id}, email: {user_email}")
        
        return {
            "message": "Your account and all associated data have been permanently deleted from all systems.",
            "details": {
                "profile_data_deleted": True,
                "auth_access_removed": True,
                "subscription_cancelled": subscription_cancelled,
                "login_disabled": True
            },
            "deletion_date": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during account deletion for user {user_id if 'user_id' in locals() else 'unknown'}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during account deletion. Please contact support."
        )
