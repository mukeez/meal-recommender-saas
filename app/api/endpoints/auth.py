"""Authentication endpoints for the meal recommendation API.

This module contains FastAPI routes for authentication using Supabase.
"""

from fastapi import APIRouter, HTTPException, status, Request, Depends, Body
from fastapi.templating import Jinja2Templates
import httpx
import logging
from datetime import datetime, timedelta
import random, hashlib

from app.core.config import settings
from app.models.user import UpdateUserProfileRequest
from app.services.user_service import user_service, UserProfileData
from app.services.mail_service import mail_service
from app.models.auth import LoginRequest, LoginResponse, SignupRequest, SignUpResponse, VerifyOtpRequest, VerifyOtpResponse, ResetPasswordRequest
from app.api.auth_guard import auth_guard
from typing import Dict

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    summary="Authenticate user",
    description="Authenticate a user with email and password using Supabase.",
    response_model=LoginResponse,
    response_model_by_alias=False,
)
async def login(payload: LoginRequest) -> LoginResponse:
    """Authenticate a user with Supabase.

    Args:
        request: The incoming FastAPI request
        payload: Login credentials containing email and password and optional FCM token

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
            detail="An error occured while trying to log in",
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=password",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                    "Content-Type": "application/json",
                },
                json={"email": payload.email, "password": payload.password},
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
            raise HTTPException(status_code=response.status_code, detail=error_detail)

        fcm_token = payload.fcm_token
        if fcm_token:
            await user_service.update_user_profile(
                token=response.json().get("access_token"),
                user_id=response.json().get("user", {}).get("id"),
                user_data=UpdateUserProfileRequest(fcm_token=fcm_token),
            )

        logger.info(f"User {payload.email} logged in successfully")
        return response.json()

    except HTTPException:
        raise

    except httpx.RequestError as e:
        logger.error(f"Error communicating with authentication service: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error communicating with authentication service",
        )


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user with email and password (and an fcm token if available), and create their profile.",
    response_model=SignUpResponse,
)
async def signup(payload: SignupRequest) -> SignUpResponse:
    """Register a new user with Supabase and create their profile."""
    logger.info(f"Signup attempt for user: {payload.email}")

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Supabase configuration is missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during user registration",
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.SUPABASE_URL}/auth/v1/signup",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                    "Content-Type": "application/json",
                },
                json={
                    "email": payload.email,
                    "password": payload.password,
                    "options": {"emailRedirectTo": None, "shouldCreateUser": True},
                },
            )
        response_data = response.json()
        logger.info(f"Full Supabase signup response: {response_data}")

        if response.status_code not in (200, 201):
            error_detail = "Signup failed"
            try:
                if "error_code" in response_data and "msg" in response_data:
                    error_detail = response_data["msg"]
            except Exception:
                pass

            logger.warning(f"Signup failed for user {payload.email}: {error_detail}")
            raise HTTPException(status_code=response.status_code, detail=error_detail)
        user_id = (
            response_data.get("user", {}).get("id")
            or response_data.get("id")
            or response_data.get("user_id")
        )

        if not user_id:
            logger.error(
                f"Failed to get user ID from registration response: {response_data}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to extract user ID from registration response",
            )

        profile_data = UserProfileData(
            user_id=user_id,
            email=payload.email,
            display_name=payload.display_name,
            fcm_token=payload.fcm_token,
        )

        await user_service.create_profile(profile_data)
        logger.info(f"Created profile for user: {user_id}")

        await user_service.create_default_preferences(user_id)
        logger.info(f"Created default preferences for user: {user_id}")

        logger.info(f"User {payload.email} registered successfully")
        return {
            "message": "User registered successfully",
            "user": {"id": user_id, "email": payload.email},
            "session": response_data.get("session", {}),
        }

    except HTTPException as e:
        raise
    except httpx.RequestError as e:
        logger.error(f"Error communicating with Supabase: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error communicating with authentication service",
        )
    except Exception as e:
        logger.error(f"Unexpected error during signup: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during user registration",
        )


@router.patch(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="change password",
    description="Change the user's password using their current session token.",
)
async def change_password(request: Request, password: str = Body(..., embed=True, description="new user password"), user=Depends(auth_guard)) -> Dict:
    """Request a password reset for a user.

    Args:
        request: The incoming FastAPI request
        email: User's email address

    Returns:
        Confirmation message

    Raises:
        HTTPException: If the request fails
    """

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Supabase configuration is missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while trying to change the password",
        )

    try:
        token = request.headers.get("Authorization").split(" ")[1]

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{settings.SUPABASE_URL}/auth/v1/user",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },

                json={"password": password},
            )

        if response.status_code != 200:
            error_detail = "Password change failed"
            try:
                error_data = response.json()
                if "error" in error_data and "message" in error_data:
                    error_detail = error_data["message"]
            except Exception:
                pass

            logger.warning(f"Password change failed for {user}: {error_detail}")
            raise HTTPException(status_code=response.status_code, detail=error_detail)
        return {"message": "Password change successful"}

    except httpx.RequestError as e:
        logger.error(f"Error communicating with Supabase: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Error communicating with authentication service",
        )


@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    summary="Request password reset OTP",
    description="Generate and send a secure OTP for password reset.",
)
async def forgot_password(email: str = Body(..., embed=True)) -> Dict:
    """Generate and send OTP for password reset."""

    try:
        logger.info(f"Password reset OTP requested for: {email}")

        user = await user_service.get_user_by_email(email)
        # still return success response to prevent email renumeration
        if not user:
            return {"message": "An OTP has been sent to your mail."}

        # Generate a 6-digit OTP
        otp = random.randint(100000, 999999)
        hashed_otp = hashlib.sha256(str(otp).encode()).hexdigest()
        expiration_time = datetime.now() + timedelta(minutes=10)

        # Store OTP securely in the database
        await user_service.store_otp(email, hashed_otp, expiration_time)

        # Send OTP via email
        await mail_service.send_email(
            recipient=email,
            subject="Password Reset OTP",
            template_name="otp.html",  # Changed from otp_email.html to match your actual file
            context={"otp_code": otp, "otp_expiry_minutes": 10},
        )

        logger.info(f"OTP sent to {email}")
        return {"message": "An OTP has been sent to your mail."}
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"Error generating OTP for {email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request.",
        )


@router.post(
    "/verify-otp",
    status_code=status.HTTP_200_OK,
    summary="Verify OTP",
    description="Verify the OTP for password reset.",
    response_model=VerifyOtpResponse
)
async def verify_otp(request: VerifyOtpRequest) -> VerifyOtpResponse:
    """Verify the OTP for password reset."""
    try:
        logger.info(f"Verifying OTP for {request.email}")

        otp_entry = await user_service.get_otp(request.email)
        if not otp_entry:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP.")
        
        # Parse the expires_at string to datetime
        expires_at = datetime.fromisoformat(otp_entry["expires_at"].replace("Z", "+00:00"))
        
        # Check if OTP has expired
        if expires_at < datetime.now(expires_at.tzinfo):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expired OTP.")

        hashed_otp = hashlib.sha256(request.otp.encode()).hexdigest()
        if hashed_otp != otp_entry["otp_hash"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP.")

        # Generate a temporary session token
        session_token = hashlib.sha256(f"{request.email}{datetime.now().isoformat()}".encode()).hexdigest()
        await user_service.store_session_token(request.email, session_token)

        logger.info(f"OTP verified for {request.email}")
        return {"message": "OTP verified.", "session_token": session_token}
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"Error verifying OTP for {request.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request.",
        )


@router.post(
    "/reset-password",
    status_code=status.HTTP_200_OK,
    summary="Reset password",
    description="Reset the user's password using a verified OTP or session token.",
)
async def reset_password(
    request: ResetPasswordRequest
) -> Dict:
    """Reset the user's password."""
    logger.info(f"Resetting password for {request.email}")

    session_entry = await user_service.get_session_token(request.email)
    # Fix this line - use dictionary access with brackets instead of dot notation
    if not session_entry or session_entry["token"] != request.session_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session token.")

    # Update the user's password
    await user_service.update_password(email=request.email, password=request.new_password)

    # Invalidate the OTP/session token
    await user_service.invalidate_otp(request.email)
    await user_service.invalidate_session_token(request.email)

    logger.info(f"Password reset successful for {request.email}")
    return {"message": "Password reset successful."}
