"""Services for user profile management.

This module provides functions to manage user profiles in the database.
"""
from typing import Dict, Any, Optional
import logging
from datetime import datetime

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel

from app.core.config import settings

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
                "is_active": True
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/rest/v1/user_profiles",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation"
                    },
                    json=profile_record
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
                        detail=f"Failed to create user profile: {error_detail}"
                    )

                logger.info(f"Profile created successfully for user: {profile_data.user_id}")
                return response.json()

        except httpx.RequestError as e:
            logger.error(f"Request error creating profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error creating profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating user profile: {str(e)}"
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
                "updated_at": datetime.now().isoformat()
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/rest/v1/user_preferences",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation"
                    },
                    json=default_preferences
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
                        detail=f"Failed to create user preferences: {error_detail}"
                    )

                logger.info(f"Default preferences created for user: {user_id}")
                return response.json()

        except httpx.RequestError as e:
            logger.error(f"Request error creating preferences: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error creating preferences: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating user preferences: {str(e)}"
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
                        "Content-Type": "application/json"
                    },
                    params={
                        "user_id": f"eq.{user_id}"
                    }
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
                        detail=f"Failed to retrieve user preferences: {error_detail}"
                    )

                preferences_data = response.json()
                if not preferences_data:
                    return {
                        "user_id": user_id,
                        "calorie_target": 2000,
                        "protein_target": 150,
                        "carbs_target": 200,
                        "fat_target": 70
                    }

                return preferences_data[0]

        except httpx.RequestError as e:
            logger.error(f"Request error retrieving preferences: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error retrieving preferences: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving user preferences: {str(e)}"
            )


user_service = UserProfileService()