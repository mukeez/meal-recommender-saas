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
                        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
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

                    logger.error(f"Session token invalidation failed for {email}: {error_detail}")
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
                response = await client.post(
                    f"{self.base_url}/rest/v1/session_tokens",
                    headers={
                        "apikey": self.api_key,
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    json=session_data,
                )

                if response.status_code not in (201, 200):
                    error_detail = "Failed to store session token"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(f"Session token storage failed for {email}: {error_detail}")
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
                detail=f"Error storing session token",
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
                    params={"email": f"eq.{email}"}
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

    async def store_otp(self, email: str, hashed_otp: str, expiration_time: datetime) -> None:
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
                "created_at": datetime.now().isoformat()
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
                    params={"email": f"eq.{email}"}
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
                        json=otp_data
                    )
                    
                    if update_response.status_code not in (200, 204):
                        logger.error(f"Failed to update OTP for {email}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to update OTP"
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
                        json=otp_data
                    )
                    
                    if create_response.status_code not in (201, 200):
                        logger.error(f"Failed to create OTP for {email}")
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to create OTP"
                        )
                
                logger.info(f"OTP stored successfully for user: {email}")
                
        except httpx.RequestError as e:
            logger.error(f"Request error storing OTP: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error communicating with database"
            )
        except Exception as e:
            logger.error(f"Unexpected error storing OTP: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error storing OTP"
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
                    params={"email": f"eq.{email}"}
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
                    params={"email": f"eq.{email}"}
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

user_service = UserProfileService()
