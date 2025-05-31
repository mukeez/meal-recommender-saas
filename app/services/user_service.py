"""Services for user profile management.

This module provides functions to manage user profiles in the database.
"""

from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.models.user import UpdateUserProfileRequest, UserProfile
from app.utils.helper_functions import remove_null_values

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
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY

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
                "calorie_target": 2000,
                "protein_target": 150,
                "carbs_target": 200,
                "fat_target": 70,
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
                        "calorie_target": 2000,
                        "protein_target": 150,
                        "carbs_target": 200,
                        "fat_target": 70,
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

    async def get_user_profile(self, user_id: str) -> str | None:
        """Retrieve user profile.

        Args:
            user_id: Supabase user ID

        Returns:
            User profile

        Raises:
            HTTPException: If there is an error retrieving the preferences
        """
        logger.info(f"Retrieving profile for user: {user_id}")

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

                profile_data = response.json()[0]
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
        self, token: str, user_id: str, user_data: UpdateUserProfileRequest
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

                if "email" in user_profile.keys():
                    await self.update_user_auth_email(
                        token=token, user_id=user_id, email=user_profile["email"]
                    )
                    time.sleep(5)

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

        try:
            filename = f"{user_id}/avatar.png"
            storage_url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.SUPABASE_BUCKET_NAME}/{filename}"
            avatar_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{settings.SUPABASE_BUCKET_NAME}/{filename}"

            async with httpx.AsyncClient() as client:
                response = await client.put(
                    storage_url,
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": content_type,
                    },
                    content=file_content,
                )

                if response.status_code not in (200, 201, 204):
                    error_detail = "Failed to upload user avatar"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Uploading avatar failed: {str(error_detail)}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to upload user avatar",
                    )

                return avatar_url

        except httpx.RequestError as e:
            logger.error(f"Error communicating with database: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to update user profile",
            )
        except Exception as e:
            logger.error(f"Unexpected error uploading user avatar {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload user avatar",
            )

    async def update_user_auth_email(
        self, token: str, user_id: str, email: str
    ) -> Optional[str]:
        try:
            logger.info(f"updating auth details for user:{user_id}:{email}")
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}",
                    headers={
                        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
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


user_service = UserProfileService()
