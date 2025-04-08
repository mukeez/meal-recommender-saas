"""Authentication endpoints for the meal recommendation API.

This module contains FastAPI routes for authentication using Supabase.
"""
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field, validator
import httpx
import logging
from typing import Optional

from app.core.config import settings
from app.services.user_service import user_service, UserProfileData

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request model.

    Attributes:
        email: User's email address
        password: User's password
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class SignupRequest(BaseModel):
    """Signup request model with basic validation.

    Attributes:
        email: User's email address
        password: User's password
        display_name: User's display name (optional)
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=6, description="User's password (min 6 characters)")
    display_name: Optional[str] = Field(None, description="User's display name")

    @validator('password')
    def validate_password_length(cls, value):
        """Validate password meets minimum length requirement."""
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return value


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    summary="Authenticate user",
    description="Authenticate a user with email and password using Supabase."
)
async def login(payload: LoginRequest):
    """Authenticate a user with Supabase.

    Args:
        request: The incoming FastAPI request
        payload: Login credentials containing email and password

    Returns:
        The authentication response from Supabase, including access token and user data

    Raises:
        HTTPException: If authentication fails
    """
    logger.info(f"Login attempt for user: {payload.email}")

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Supabase configuration is missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase configuration is missing. Please check your environment variables."
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=password",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                    "Content-Type": "application/json"
                },
                json={"email": payload.email, "password": payload.password}
            )

        if response.status_code != 200:
            error_detail = "Login failed"
            try:
                error_data = response.json()
                if "error" in error_data and "message" in error_data:
                    error_detail = error_data["message"]
            except Exception:
                pass

            logger.warning(f"Login failed for user {payload.email}: {error_detail}")
            raise HTTPException(
                status_code=response.status_code,
                detail=error_detail
            )

        logger.info(f"User {payload.email} logged in successfully")
        return response.json()  # includes access_token, user, etc.

    except httpx.RequestError as e:
        logger.error(f"Error communicating with Supabase: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error communicating with authentication service: {str(e)}"
        )


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user with email and password, and create their profile."
)
async def signup(payload: SignupRequest):
    """Register a new user with Supabase and create their profile."""
    logger.info(f"Signup attempt for user: {payload.email}")

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Supabase configuration is missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase configuration is missing"
        )

    try:
        # Register the user with Supabase Auth
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.SUPABASE_URL}/auth/v1/signup",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                    "Content-Type": "application/json"
                },
                json={"email": payload.email, "password": payload.password}
            )
        print(response.json())
        response_data = response.json()
        logger.info(f"Full Supabase signup response: {response_data}")

        if response.status_code not in (200, 201):
            error_detail = "Signup failed"
            try:
                if "error" in response_data and "message" in response_data:
                    error_detail = response_data["message"]
            except Exception:
                pass

            logger.warning(f"Signup failed for user {payload.email}: {error_detail}")
            raise HTTPException(
                status_code=response.status_code,
                detail=error_detail
            )

        # More robust user ID extraction
        user_id = (
                response_data.get('user', {}).get('id') or
                response_data.get('id') or
                response_data.get('user_id')
        )

        if not user_id:
            logger.error(f"Failed to get user ID from registration response: {response_data}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to extract user ID from registration response"
            )

        # Create the user profile
        profile_data = UserProfileData(
            user_id=user_id,
            email=payload.email,
            display_name=payload.display_name
        )

        await user_service.create_profile(profile_data)
        logger.info(f"Created profile for user: {user_id}")

        # Create default user preferences
        await user_service.create_default_preferences(user_id)
        logger.info(f"Created default preferences for user: {user_id}")

        # Return the Supabase authentication response with additional information
        logger.info(f"User {payload.email} registered successfully")
        return {
            "message": "User registered successfully",
            "user": {
                "id": user_id,
                "email": payload.email
            },
            "session": response_data.get('session', {})
        }

    except httpx.RequestError as e:
        logger.error(f"Error communicating with Supabase: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error communicating with authentication service: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during signup: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during user registration: {str(e)}"
        )


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="Send a password reset email to the user."
)
async def request_password_reset(request: Request, email: str):
    """Request a password reset for a user.

    Args:
        request: The incoming FastAPI request
        email: User's email address

    Returns:
        Confirmation message

    Raises:
        HTTPException: If the request fails
    """
    logger.info(f"Password reset requested for: {email}")

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Supabase configuration is missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase configuration is missing"
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.SUPABASE_URL}/auth/v1/recover",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                    "Content-Type": "application/json"
                },
                json={"email": email}
            )

        if response.status_code != 200:
            error_detail = "Password reset request failed"
            try:
                error_data = response.json()
                if "error" in error_data and "message" in error_data:
                    error_detail = error_data["message"]
            except Exception:
                pass

            logger.warning(f"Password reset failed for {email}: {error_detail}")
            raise HTTPException(
                status_code=response.status_code,
                detail=error_detail
            )

        logger.info(f"Password reset email sent to: {email}")
        return {"message": "Password reset instructions sent to your email"}

    except httpx.RequestError as e:
        logger.error(f"Error communicating with Supabase: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error communicating with authentication service: {str(e)}"
        )