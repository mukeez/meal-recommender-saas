"""User endpoints for the meal recommendation API.

This module contains FastAPI routes for user-related functionality.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Form, UploadFile, File
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
)
from app.services.user_service import user_service
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/me",
    summary="Get current user profile",
    description="Retrieve the profile of the currently authenticated user.",
    response_model=UserProfile,
    response_model_by_alias=False
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
    response_model_by_alias=False,
)
async def update_user_profile(
    email: Optional[str] = Form(None, description="new user email (optional)"),
    display_name: Optional[str] = Form(
        None, description="new user display name (optional)"
    ),
    first_name: Optional[str] = Form(
        None, description="new user first name (optional)"
    ),
    last_name: Optional[str] = Form(None, description="new user last name (optional)"),
    avatar: Optional[UploadFile] = File(
        None, description="new user profile (optional)"
    ),
    user=Depends(auth_guard),
) -> UserProfile:
    """Update the current user's profile.

    This is a protected endpoint that requires authentication.

    Args:
        user: The authenticated user (injected by the auth_guard dependency)
        display_name: new user email(optional)
        email: new user email(optional)
        first_name: new user first name(optional)
        last_name: new user last name(optional)
        avatar: new user avatar(optional)

    Returns:
        The user profile information
    """
    try:
        user_id = user.get("sub")
        if avatar:
            if not avatar.content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="Only image files allowed.")
            file_content = await avatar.read()
            content_type = avatar.content_type
            avatar_url = await user_service.upload_user_avatar(
                user_id=user_id, file_content=file_content, content_type=content_type
            )
            await avatar.close()
            user_data = UpdateUserProfileRequest(
                display_name=display_name,
                email=email,
                first_name=first_name,
                last_name=last_name,
                avatar_url=avatar_url,
            )
        else:
            user_data = UpdateUserProfileRequest(
                display_name=display_name,
                email=email,
                first_name=first_name,
                last_name=last_name,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving preferences: {str(e)}",
        )


@router.patch(
    "/preferences",
    response_model=UserPreferences,
    status_code=status.HTTP_200_OK,
    summary="Update user preferences",
    description="Update the current user's dietary preferences and macro targets.",
)
async def update_user_preferences(
    preferences_update: UpdateUserPreferencesRequest, user=Depends(auth_guard)
):
    """
    Update the current user's preferences.

    Args:
        preferences_update: Partial update to user preferences
        user: Authenticated user from auth_guard

    Returns:
        Updated UserPreferences object
    """
    try:
        user_id = user.get("sub")

        update_data = {
            k: v
            for k, v in preferences_update.dict(exclude_unset=True).items()
            if v is not None
        }

        update_data["updated_at"] = datetime.utcnow().isoformat()

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
