"""Services for user profile management.

This module provides functions to manage user profiles in the database.
"""

from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import random
import hashlib

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.models.user import (
    UpdateUserProfileRequest,
    UserProfile,
    HeightUnitPreference,
    WeightUnitPreference,
)
from app.utils.helper_functions import remove_null_values
from app.utils.constants import CM_TO_FEET, FEET_TO_CM, KG_TO_LBS, LBS_TO_KG
from app.utils.file_upload import (
    upload_file_to_bucket,
    generate_avatar_path,
    validate_image_file,
)
from app.utils.slack import send_slack_alert

import time

logger = logging.getLogger(__name__)


class UserProfileData(BaseModel):
    """User profile data model.

    Attributes:
        user_id: Supabase user ID
        email: User's email address
        display_name: User's display name (optional)
        created_at: Profile creation timestamp
    """

    user_id: str
    email: str
    display_name: Optional[str] = None
    fcm_token: Optional[str] = None
    created_at: datetime = datetime.now()


class UserProfileService:
    """Service for managing user profiles."""

    def __init__(self):
        """Initialize the user profile service."""
        self.base_url = settings.SUPABASE_URL

        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError("SUPABASE_SERVICE_ROLE_KEY is required")

        self.api_key: str = settings.SUPABASE_SERVICE_ROLE_KEY

    async def create_profile(self, profile_data: UserProfileData) -> Dict[str, Any]:
        """Create a new user profile in the database.

        Args:
            profile_data: User profile data to be stored

        Returns:
            The created profile record

        Raises:
            HTTPException: If there is an error creating the profile
        """
        logger.info(f"Creating profile for user: {profile_data.user_id}")

        try:
            profile_record = {
                "id": profile_data.user_id,
                "email": profile_data.email,
                "display_name": profile_data.display_name,
                "created_at": profile_data.created_at.isoformat(),
                "updated_at": profile_data.created_at.isoformat(),
                "is_active": True,
                "email_verified": False,
                "fcm_token": profile_data.fcm_token,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/rest/v1/user_profiles",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    json=profile_record,
                )

                if response.status_code not in (201, 200):
                    error_detail = "Failed to create user profile"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Profile creation failed: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to create user profile",
                    )

                logger.info(
                    f"Profile created successfully for user: {profile_data.user_id}"
                )
                return response.json()

        except httpx.RequestError as e:
            logger.error(f"Request error creating profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error creating profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating user profile",
            )

    async def create_default_preferences(self, user_id: str) -> Dict[str, Any]:
        """Create default dietary preferences for a new user.

        Args:
            user_id: Supabase user ID

        Returns:
            The created preferences record

        Raises:
            HTTPException: If there is an error creating the preferences
        """
        logger.info(f"Creating default preferences for user: {user_id}")

        try:
            default_preferences = {
                "user_id": user_id,
                "dietary_restrictions": [],
                "favorite_cuisines": [],
                "disliked_ingredients": [],
                "calorie_target": 0,
                "protein_target": 0,
                "carbs_target": 0,
                "fat_target": 0,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/rest/v1/user_preferences",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    json=default_preferences,
                )

                if response.status_code not in (201, 200):
                    error_detail = "Failed to create user preferences"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Preferences creation failed: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to create user preferences",
                    )

                logger.info(f"Default preferences created for user: {user_id}")
                return response.json()

        except httpx.RequestError as e:
            logger.error(f"Request error creating preferences: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error creating preferences: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating user preferences",
            )

    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Retrieve user preferences.

        Args:
            user_id: Supabase user ID

        Returns:
            User preferences dictionary

        Raises:
            HTTPException: If there is an error retrieving the preferences
        """
        logger.info(f"Retrieving preferences for user: {user_id}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/v1/user_preferences",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"user_id": f"eq.{user_id}"},
                )

                if response.status_code not in (200, 201, 204):
                    error_detail = "Failed to retrieve user preferences"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Preferences retrieval failed: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to retrieve user preferences",
                    )

                preferences_data = response.json()
                if not preferences_data:
                    return {
                        "user_id": user_id,
                        "calorie_target": 0,
                        "protein_target": 0,
                        "carbs_target": 0,
                        "fat_target": 0,
                    }

                return preferences_data[0]

        except httpx.RequestError as e:
            logger.error(f"Request error retrieving preferences: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error retrieving preferences: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving user preferences",
            )

    async def get_user_profile(self, user_id: str) -> UserProfile:
        """Retrieve user profile with unit preferences.

        Args:
            user_id: Supabase user ID

        Returns:
            User profile with unit preference information

        Raises:
            HTTPException: If there is an error retrieving the profile
        """
        logger.info(f"Retrieving profile for user: {user_id}")

        try:
            # Get the basic profile
            profile_data = await self._get_basic_profile(user_id)

            # Get user preferences to include unit preference
            user_preferences = await self.get_user_preferences(user_id)

            # Check if calorie_target exists and update has_macros if needed
            if (
                user_preferences
                and user_preferences.get("calorie_target")
                and not profile_data.get("has_macros")
            ):
                profile_data = await self._update_has_macros(user_id, profile_data)

            # Convert stored metric values to user's preferred units for display
            if (
                profile_data.get("height_unit_preference")
                == HeightUnitPreference.IMPERIAL
            ):
                if profile_data["height"]:
                    profile_data["height"] = round(
                        profile_data["height"] * CM_TO_FEET, 2
                    )

            if (
                profile_data.get("weight_unit_preference")
                == WeightUnitPreference.IMPERIAL
            ):
                if profile_data["weight"]:
                    profile_data["weight"] = round(
                        profile_data["weight"] * KG_TO_LBS, 2
                    )

            return UserProfile(**profile_data)

        except httpx.RequestError as e:
            logger.error(f"Request error retrieving profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error retrieving profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving user profile: {str(e)}",
            )

    async def update_user_profile(
        self, user_id: str, user_data: UpdateUserProfileRequest
    ) -> UserProfile:
        """Update user profile.

        Args:
            user_id: Supabase user ID
            user_data: User data to be updated

        Returns:
            User preferences dictionary

        Raises:
            HTTPException: If there is an error updating user profile
        """
        logger.info(f"Updating profile for user: {user_id}")

        try:
            user_profile = remove_null_values(user_data.model_dump())

            # Convert user input to metric units for database storage
            if "height" in user_profile.keys():
                if (
                    user_profile.get("height_unit_preference")
                    == HeightUnitPreference.IMPERIAL
                ):
                    # Convert height from feet to cm
                    user_profile["height"] = round(
                        user_profile["height"] * FEET_TO_CM, 2
                    )

            if "weight" in user_profile.keys():
                if (
                    user_profile.get("weight_unit_preference")
                    == WeightUnitPreference.IMPERIAL
                ):
                    # Convert weight from lbs to kg
                    user_profile["weight"] = round(
                        user_profile["weight"] * LBS_TO_KG, 2
                    )

            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/rest/v1/user_profiles",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    params={"id": f"eq.{user_id}"},
                    json=user_profile,
                )

                if response.status_code not in (200, 201, 204):
                    error_detail = "Failed to update user profile"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Update profile failed: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to update user profile",
                    )
                response_data = response.json()[0]
                return UserProfile(**response_data)

        except httpx.RequestError as e:
            logger.error(f"Error communicating with database: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to update user profile",
            )
        except Exception as e:
            logger.error(f"Unexpected error updating user profile {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update user profile",
            )

    async def upload_user_avatar(
        self, user_id: str, file_content: bytes, content_type: str
    ) -> Optional[str]:
        """Upload user avatar to supabase bucket.

        Args:
            user_id: Supabase user ID
            file_content: image (bytes) to upload
            content_type: content type (image)

        Returns:
            public url to image

        Raises:
            HTTPException: If there is an error uploading user avatar
        """

        logger.info(f"Upload avatar for user: {user_id}")

        # Validate the image file
        validate_image_file(None, content_type)

        # Generate the file path
        file_extension = "png" if content_type == "image/png" else "jpg"
        file_path = generate_avatar_path(user_id, file_extension)

        # Upload using the generalized function
        return await upload_file_to_bucket(file_content, file_path, content_type)

    async def update_user_auth_email(
        self, token: str, user_id: str, email: str
    ) -> Optional[str]:
        try:
            logger.info(f"updating auth details for user:{user_id}:{email}")
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"email": email},
                )

                if response.status_code not in (200, 201, 204):
                    error_detail = "Failed to update auth details"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Updating user details failed: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to update user auth details: {error_detail}",
                    )
                return "success"

        except httpx.RequestError as e:
            logger.error(f"Request error updating user auth details: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error updating user auth details {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error uploading user auth details",
            )

    async def update_fcm_token(self, user_id: str, fcm_token: str) -> None:
        """Update FCM token for the user.

        Args:
            user_id: Supabase user ID
            fcm_token: FCM token to be updated

        Raises:
            HTTPException: If there is an error updating the FCM token
        """
        logger.info(f"Updating FCM token for user: {user_id}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/rest/v1/user_profiles",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    params={"id": f"eq.{user_id}"},
                    json={"fcm_token": fcm_token},
                )

                if response.status_code not in (200, 201, 204):
                    error_detail = "Failed to update FCM token"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Updating FCM token failed: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to update FCM token",
                    )

                logger.info(f"FCM token updated successfully for user: {user_id}")

        except httpx.RequestError as e:
            logger.error(f"Request error updating FCM token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error updating FCM token {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update FCM token",
            )

    async def mark_trial_as_used(self, user_id: str) -> None:
        """Mark the user's trial as used.

        Args:
            user_id: Supabase user ID

        Raises:
            HTTPException: If there is an error updating the trial status
        """
        logger.info(f"Marking trial as used for user: {user_id}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.base_url}/rest/v1/user_profiles",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    params={"id": f"eq.{user_id}"},
                    json={"has_used_trial": True},
                )

                if response.status_code not in (200, 201, 204):
                    error_detail = "Failed to update trial status"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Updating trial status failed: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to update trial status",
                    )

                logger.info(f"Trial status updated successfully for user: {user_id}")

        except httpx.RequestError as e:
            logger.error(f"Request error updating trial status: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error updating trial status {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update trial status",
            )

    async def update_password(self, email: str, password: str) -> None:
        """Update the user's password in the database."""
        logger.info(f"Updating password for user: {email}")

        try:
            async with httpx.AsyncClient() as client:
                user = await self.get_user_by_email(email=email)
                user_id = user.get("id") if user else None
                response = await client.put(
                    f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"password": password},
                )

                if response.status_code not in (200, 204):
                    error_detail = "Failed to update password"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Password update failed for {email}: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to update password",
                    )

                logger.info(f"Password updated successfully for user: {email}")

        except httpx.RequestError as e:
            logger.error(f"Request error updating password: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error updating password: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error updating password",
            )

    async def invalidate_session_token(self, email: str) -> None:
        """Invalidate the session token for the user."""
        logger.info(f"Invalidating session token for user: {email}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/rest/v1/session_tokens",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"email": f"eq.{email}"},
                )

                if response.status_code not in (200, 204):
                    error_detail = "Failed to invalidate session token"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(
                        f"Session token invalidation failed for {email}: {error_detail}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to invalidate session token",
                    )

                logger.info(f"Session token invalidated successfully for user: {email}")

        except httpx.RequestError as e:
            logger.error(f"Request error invalidating session token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error invalidating session token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error invalidating session token",
            )

    async def get_otp(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieve the OTP entry for the user."""
        logger.info(f"Retrieving OTP for user: {email}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/v1/otp",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"email": f"eq.{email}"},
                )

                if response.status_code not in (200, 204):
                    error_detail = "Failed to retrieve OTP"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"OTP retrieval failed for {email}: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to retrieve OTP",
                    )

                otp_data = response.json()
                return otp_data[0] if otp_data else None

        except httpx.RequestError as e:
            logger.error(f"Request error retrieving OTP: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error retrieving OTP: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving OTP",
            )

    async def store_session_token(self, email: str, session_token: str) -> None:
        """Store the session token for the user."""
        logger.info(f"Storing session token for user: {email}")

        try:
            session_data = {
                "email": email,
                "token": session_token,
                "created_at": datetime.now().isoformat(),
            }

            async with httpx.AsyncClient() as client:
                # First check if a token already exists for this email
                check_response = await client.get(
                    f"{self.base_url}/rest/v1/session_tokens",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"email": f"eq.{email}"},
                )

                if check_response.status_code == 200 and check_response.json():
                    # Token exists, update it
                    update_response = await client.patch(
                        f"{self.base_url}/rest/v1/session_tokens",
                        headers={
                            "apikey": self.api_key,
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "Prefer": "return=representation",
                        },
                        params={"email": f"eq.{email}"},
                        json=session_data,
                    )

                    if update_response.status_code not in (200, 204):
                        error_detail = "Failed to update session token"
                        try:
                            error_data = update_response.json()
                            if "message" in error_data:
                                error_detail = error_data["message"]
                        except Exception:
                            pass

                        logger.error(
                            f"Session token update failed for {email}: {error_detail}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to update session token",
                        )
                else:
                    # No token exists, create a new one
                    create_response = await client.post(
                        f"{self.base_url}/rest/v1/session_tokens",
                        headers={
                            "apikey": self.api_key,
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "Prefer": "return=representation",
                        },
                        json=session_data,
                    )

                    if create_response.status_code not in (201, 200):
                        error_detail = "Failed to store session token"
                        try:
                            error_data = create_response.json()
                            if "message" in error_data:
                                error_detail = error_data["message"]
                        except Exception:
                            pass

                        logger.error(
                            f"Session token storage failed for {email}: {error_detail}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to store session token",
                        )

            logger.info(f"Session token stored successfully for user: {email}")

        except httpx.RequestError as e:
            logger.error(f"Request error storing session token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error storing session token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store session token",
            )

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user by their email address from user_profiles table.

        Args:
            email: The email address of the user to retrieve

        Returns:
            User data dictionary if found, None otherwise

        Raises:
            HTTPException: If there's an error communicating with the database
        """
        logger.info(f"Retrieving user with email: {email}")

        try:
            async with httpx.AsyncClient() as client:
                # Check user_profiles table for the user
                response = await client.get(
                    f"{self.base_url}/rest/v1/user_profiles",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"email": f"eq.{email}"},
                )

                if response.status_code == 200:
                    profiles = response.json()
                    if profiles and len(profiles) > 0:
                        return profiles[0]

                # User not found
                logger.info(f"No user found with email: {email}")
                return None

        except httpx.RequestError as e:
            logger.error(f"Request error retrieving user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error retrieving user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving user data",
            )

    async def store_otp(
        self, email: str, hashed_otp: str, expiration_time: datetime
    ) -> None:
        """
        Store the OTP (One-Time Password) for the user's password reset request.

        Args:
            email: The user's email address
            hashed_otp: The SHA-256 hash of the OTP (not the actual OTP)
            expiration_time: When the OTP expires

        Raises:
            HTTPException: If there's an error communicating with the database
        """
        logger.info(f"Storing OTP for user: {email}")

        try:
            otp_data = {
                "email": email,
                "otp_hash": hashed_otp,
                "expires_at": expiration_time.isoformat(),
                "created_at": datetime.now().isoformat(),
            }

            async with httpx.AsyncClient() as client:
                # First check if an OTP already exists for this email
                check_response = await client.get(
                    f"{self.base_url}/rest/v1/otp",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"email": f"eq.{email}"},
                )

                if check_response.status_code == 200 and check_response.json():
                    # OTP exists, update it
                    update_response = await client.patch(
                        f"{self.base_url}/rest/v1/otp",
                        headers={
                            "apikey": self.api_key,
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "Prefer": "return=representation",
                        },
                        params={"email": f"eq.{email}"},
                        json=otp_data,
                    )

                    if update_response.status_code not in (200, 204):
                        logger.error(f"Failed to update OTP for {email}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to update OTP",
                        )
                else:
                    # No OTP exists, create a new one
                    create_response = await client.post(
                        f"{self.base_url}/rest/v1/otp",
                        headers={
                            "apikey": self.api_key,
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "Prefer": "return=representation",
                        },
                        json=otp_data,
                    )

                    if create_response.status_code not in (201, 200):
                        logger.error(f"Failed to create OTP for {email}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to create OTP",
                        )

                logger.info(f"OTP stored successfully for user: {email}")

        except httpx.RequestError as e:
            logger.error(f"Request error storing OTP: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error storing OTP: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error storing OTP",
            )

    async def get_session_token(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve the session token entry for a user.

        Args:
            email: The email address of the user

        Returns:
            Dictionary containing session token data if found, None otherwise

        Raises:
            HTTPException: If there's an error communicating with the database
        """
        logger.info(f"Retrieving session token for user: {email}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/v1/session_tokens",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"email": f"eq.{email}"},
                )

                if response.status_code == 200:
                    tokens = response.json()
                    if tokens and len(tokens) > 0:
                        return tokens[0]

            # No token found
            logger.info(f"No session token found for user: {email}")
            return None

        except httpx.RequestError as e:
            logger.error(f"Request error retrieving session token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error retrieving session token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving session token",
            )

    async def invalidate_otp(self, email: str) -> None:
        """
        Invalidate (delete) the OTP entry for the user.

        Args:
            email: The email address of the user

        Raises:
            HTTPException: If there's an error communicating with the database
        """
        logger.info(f"Invalidating OTP for user: {email}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.base_url}/rest/v1/otp",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"email": f"eq.{email}"},
                )

                if response.status_code not in (200, 204):
                    error_detail = "Unknown error"
                    try:
                        error_detail = response.json().get("message", "Unknown error")
                    except:
                        pass

                    logger.error(f"OTP invalidation failed for {email}: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to invalidate OTP",
                    )

                logger.info(f"OTP invalidated successfully for user: {email}")

        except httpx.RequestError as e:
            logger.error(f"Request error invalidating OTP: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database",
            )
        except Exception as e:
            logger.error(f"Unexpected error invalidating OTP: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error invalidating OTP",
            )

    async def generate_email_verification_otp(self, user_id: str, email: str) -> str:
        """
        Generate and store an OTP for email verification.

        Args:
            user_id: The user's ID
            email: The user's email address

        Returns:
            The generated OTP code

        Raises:
            HTTPException: If there's an error generating or storing the OTP
        """
        logger.info(f"Generating email verification OTP for user: {user_id}")

        try:
            # Generate 6-digit OTP
            otp_code = str(random.randint(100000, 999999))

            # Hash the OTP for storage
            hashed_otp = hashlib.sha256(otp_code.encode()).hexdigest()

            # Set expiration to 15 minutes from now
            expiration_time = datetime.now() + timedelta(minutes=15)

            # Store the OTP using existing method
            await self.store_otp(email, hashed_otp, expiration_time)

            logger.info(
                f"Email verification OTP generated successfully for user: {user_id}"
            )
            return otp_code

        except Exception as e:
            logger.error(f"Error generating email verification OTP: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate verification code",
            )

    async def send_verification_email(
        self, email: str, otp_code: str, user_name: Optional[str] = None
    ) -> None:
        """
        Send an email verification OTP to the user.

        Args:
            email: The user's email address
            otp_code: The OTP code to send
            user_name: Optional user display name

        Raises:
            HTTPException: If there's an error sending the email
        """
        from app.services.mail_service import mail_service

        logger.info(f"Sending verification email to: {email}")

        try:
            await mail_service.send_email(
                recipient=email,
                subject="Verify Your MacroMeals Account",
                template_name="email-verification.html",
                context={
                    "user_name": user_name,
                    "otp_code": otp_code,
                    "expiry_minutes": 15,
                },
            )

            logger.info(f"Verification email sent successfully to: {email}")

        except Exception as e:
            logger.error(f"Error sending verification email: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send verification email",
            )

    async def validate_otp(self, email: str, otp: str) -> bool:
        """
        Validate an OTP for a user.

        Args:
            email: The user's email address
            otp: The OTP code to validate

        Returns:
            True if OTP is valid, False otherwise
        """
        try:
            otp_entry = await self.get_otp(email)
            if not otp_entry:
                return False

            # Parse the expires_at string to datetime
            expires_at = datetime.fromisoformat(
                otp_entry["expires_at"].replace("Z", "+00:00")
            )

            # Check if OTP has expired
            if expires_at < datetime.now(expires_at.tzinfo):
                return False

            hashed_otp = hashlib.sha256(otp.encode()).hexdigest()
            return hashed_otp == otp_entry["otp_hash"]

        except Exception as e:
            logger.error(f"Error validating OTP: {str(e)}")
            return False

    async def verify_email_with_otp(self, email: str, otp: str) -> bool:
        """
        Verify a user's email address using OTP.

        Args:
            email: The user's email address
            otp: The OTP code provided by the user

        Returns:
            True if verification was successful, False otherwise

        Raises:
            HTTPException: If there's an error during verification
        """
        logger.info(f"Verifying email with OTP for: {email}")

        try:
            # Validate OTP using existing method
            is_valid = await self.validate_otp(email, otp)

            if not is_valid:
                logger.warning(f"Invalid OTP for email verification: {email}")
                return False

            # Update user as verified
            async with httpx.AsyncClient() as client:
                update_response = await client.patch(
                    f"{self.base_url}/rest/v1/user_profiles",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"email": f"eq.{email}"},
                    json={"email_verified": True},
                )

                if update_response.status_code not in (200, 204):
                    logger.error(f"Failed to update user verification status: {email}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to complete email verification",
                    )

            # Invalidate the OTP after successful verification
            await self.invalidate_otp(email)

            logger.info(f"Email verified successfully with OTP for: {email}")
            return True

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error verifying email with OTP: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error verifying email",
            )

    async def _get_basic_profile(self, user_id: str) -> Dict[str, Any]:
        """Private method to retrieve basic user profile data.

        Args:
            user_id: Supabase user ID

        Returns:
            Basic user profile data

        Raises:
            HTTPException: If there is an error retrieving the profile
        """
        logger.info(f"Retrieving basic profile for user: {user_id}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/rest/v1/user_profiles",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params={"id": f"eq.{user_id}"},
                )

                if response.status_code not in (200, 201, 204):
                    error_detail = "Failed to retrieve user profile"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Profile retrieval failed: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to retrieve user profile",
                    )

                return response.json()[0]

        except httpx.RequestError as e:
            logger.error(f"Request error retrieving profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error retrieving profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving user profile: {str(e)}",
            )

    async def _update_has_macros(
        self, user_id: str, profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update has_macros field based on user profile data.

        Args:
            user_id: User ID
            profile_data: User profile data

        Returns:
            Updated profile data with has_macros field
        """
        # Check if user has macro-related data
        has_macros = any(
            [
                profile_data.get("age"),
                profile_data.get("height"),
                profile_data.get("weight"),
                profile_data.get("sex"),
            ]
        )

        if has_macros:
            profile_data["has_macros"] = True

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.patch(
                        f"{self.base_url}/rest/v1/user_profiles",
                        headers={
                            "apikey": self.api_key,
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                            "Prefer": "return=representation",
                        },
                        params={"id": f"eq.{user_id}"},
                        json={"has_macros": True},
                    )

                    if response.status_code not in (200, 201):
                        logger.warning(
                            f"Failed to update has_macros for user {user_id}"
                        )

            except Exception as e:
                logger.warning(
                    f"Error updating has_macros for user {user_id}: {str(e)}"
                )

        return profile_data

    async def delete_user_account(self, user_id: str) -> None:
        """Permanently delete all user data from all tables.

        This method deletes user data from all related tables:
        - user_profiles
        - user_preferences
        - meal_logs
        - notifications
        - And any other user-related data

        Args:
            user_id: The user ID to delete all data for

        Raises:
            HTTPException: If deletion fails
        """
        try:
            logger.info(f"Starting complete data deletion for user: {user_id}")

            if not self.api_key:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Service configuration error",
                )

            # List of tables to delete user data from
            tables_to_delete = [
                "meal_logs",
                "notifications",
                "user_preferences",
                "user_profiles",
            ]

            deletion_results = {}

            async with httpx.AsyncClient() as client:
                for table in tables_to_delete:
                    try:
                        logger.info(f"Deleting user data from table: {table}")

                        if table == "user_profiles":
                            params = {"id": f"eq.{user_id}"}
                        else:
                            params = {"user_id": f"eq.{user_id}"}

                        response = await client.delete(
                            f"{self.base_url}/rest/v1/{table}",
                            headers={
                                "apikey": self.api_key,
                                "Authorization": f"Bearer {self.api_key}",
                                "Content-Type": "application/json",
                                "Prefer": "return=representation",
                            },
                            params=params,
                        )

                        if response.status_code in (200, 204):
                            deleted_records = (
                                response.json() if response.content else []
                            )
                            record_count = (
                                len(deleted_records)
                                if isinstance(deleted_records, list)
                                else 0
                            )
                            deletion_results[table] = record_count
                            logger.info(
                                f"Successfully deleted {record_count} records from {table}"
                            )
                        elif response.status_code == 404:
                            # Table might not exist or no records found
                            deletion_results[table] = 0
                            logger.info(
                                f"No records found in {table} for user {user_id}"
                            )
                        else:
                            logger.error(
                                f"Failed to delete from {table}: {response.status_code} - {response.text}"
                            )
                            deletion_results[table] = "failed"

                    except Exception as e:
                        logger.error(f"Error deleting from table {table}: {str(e)}")
                        deletion_results[table] = "error"

                # Delete user from Supabase Auth (this removes login capability)
                try:
                    logger.info(
                        f"CRITICAL STEP: Deleting user from Supabase Auth: {user_id}"
                    )

                    auth_response = await client.delete(
                        f"{self.base_url}/auth/v1/admin/users/{user_id}",
                        headers={
                            "apikey": self.api_key,
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                    )

                    if auth_response.status_code in (200, 204):
                        logger.info(
                            f"✅ SUCCESS: Auth user deleted from Supabase: {user_id}"
                        )
                        deletion_results["auth_user"] = "deleted"
                    elif auth_response.status_code == 404:
                        logger.info(
                            f"Auth user {user_id} not found (may have been deleted already)"
                        )
                        deletion_results["auth_user"] = "not_found"
                    else:
                        logger.error(
                            f"❌ FAILED: Auth user deletion failed - {auth_response.status_code}: {auth_response.text}"
                        )
                        deletion_results["auth_user"] = "failed"

                except Exception as e:
                    logger.error(
                        f"❌ ERROR: Exception during auth user deletion for {user_id}: {str(e)}"
                    )
                    deletion_results["auth_user"] = "error"

            logger.info(
                f"Data deletion completed for user {user_id}. Results: {deletion_results}"
            )

            # Check if critical deletions succeeded
            if deletion_results.get("user_profiles") == "failed":
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to delete user profile data",
                )

            auth_result = deletion_results.get("auth_user")
            if auth_result in ["failed", "error"]:
                logger.error(
                    f"CRITICAL WARNING: Auth user deletion failed for {user_id}. User may still be able to log in!"
                )
                send_slack_alert(
                    message=f"🚨 CRITICAL: Failed to delete user profile data during account deletion!\n"
                    f"• User ID: {user_id}\n"
                    f"• Failed Table: user_profiles\n"
                    f"• Impact: User data remains in database despite deletion request\n"
                    f"• Action Required: Manual profile data cleanup needed\n"
                    f"• Time: {datetime.now().isoformat()}\n"
                    f"• Full Results: {deletion_results}",
                    title="🚨 Critical Profile Deletion Failure",
                )
            elif auth_result in ["deleted", "not_found"]:
                logger.info(
                    f"✅ Auth user successfully removed from Supabase for {user_id}"
                )
            else:
                logger.warning(
                    f"Unexpected auth deletion result for {user_id}: {auth_result}"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error during account deletion for user {user_id}: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete user account: {str(e)}",
            )


user_service = UserProfileService()
