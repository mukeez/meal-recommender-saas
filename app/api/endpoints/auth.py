"""Authentication endpoints for the meal recommendation API.

This module contains FastAPI routes for authentication using Supabase.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, validator
import httpx

from core.config import settings

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request model.

    Attributes:
        email: User's email address
        password: User's password
    """
    email: str
    password: str

    @validator('email')
    def validate_email(cls, value):
        """Validate email format."""
        if not value or '@' not in value:
            raise ValueError("Invalid email format")
        return value

    @validator('password')
    def validate_password(cls, value):
        """Validate password is not empty."""
        if not value:
            raise ValueError("Password cannot be empty")
        return value


class SignupRequest(BaseModel):
    """Signup request model.

    Attributes:
        email: User's email address
        password: User's password
    """
    email: str
    password: str

    @validator('email')
    def validate_email(cls, value):
        """Validate email format."""
        if not value or '@' not in value:
            raise ValueError("Invalid email format")
        return value

    @validator('password')
    def validate_password(cls, value):
        """Validate password is not empty and meets minimum requirements."""
        if not value:
            raise ValueError("Password cannot be empty")
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
        payload: Login credentials containing email and password

    Returns:
        The authentication response from Supabase, including access token and user data

    Raises:
        HTTPException: If authentication fails
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase configuration is missing"
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

            raise HTTPException(
                status_code=response.status_code,
                detail=error_detail
            )

        return response.json()  # includes access_token, user, etc.

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error communicating with Supabase: {str(e)}"
        )


@router.post(
    "/signup",
    status_code=status.HTTP_200_OK,
    summary="Register a new user",
    description="Register a new user with email and password using Supabase."
)
async def signup(payload: SignupRequest):
    """Register a new user with Supabase.

    Args:
        payload: Signup credentials containing email and password

    Returns:
        The registration response from Supabase

    Raises:
        HTTPException: If registration fails
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase configuration is missing"
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.SUPABASE_URL}/auth/v1/signup",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                    "Content-Type": "application/json"
                },
                json={"email": payload.email, "password": payload.password}
            )

        if response.status_code != 200:
            error_detail = "Signup failed"
            try:
                error_data = response.json()
                if "error" in error_data and "message" in error_data:
                    error_detail = error_data["message"]
            except Exception:
                pass

            raise HTTPException(
                status_code=response.status_code,
                detail=error_detail
            )

        return response.json()

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error communicating with Supabase: {str(e)}"
        )