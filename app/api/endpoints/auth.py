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
from app.models.auth import LoginRequest, LoginResponse, SignupRequest, SignUpResponse, VerifyOtpRequest, VerifyOtpResponse, ResetPasswordRequest, VerifyEmailRequest, VerifyEmailResponse, ResendVerificationRequest, ResendVerificationResponse, RefreshTokenRequest, RefreshTokenResponse, UserMetadata
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
            error_code = None
            
            try:
                error_data = response.json()
                if "error_code" in error_data:
                    error_code = error_data["error_code"]
                if "msg" in error_data:
                    error_detail = error_data["msg"]
                elif "message" in error_data:
                    error_detail = error_data["message"]
            except Exception:
                pass

            # Handle specific error cases with user-friendly messages
            if response.status_code == 400:
                # Invalid credentials
                if error_code == "invalid_credentials" or "invalid" in error_detail.lower():
                    logger.warning(f"Invalid credentials for user {payload.email}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password. Please check your credentials and try again."
                    )
                elif "email" in error_detail.lower() and ("invalid" in error_detail.lower() or "format" in error_detail.lower()):
                    logger.warning(f"Invalid email format for login: {payload.email}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Please provide a valid email address."
                    )
                elif "password" in error_detail.lower():
                    logger.warning(f"Password validation failed for login: {payload.email}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Password cannot be empty."
                    )
                else:
                    logger.warning(f"Bad request for user {payload.email}: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid login request. Please check your email and password."
                    )
            elif response.status_code == 401:
                # Unauthorized
                logger.warning(f"Unauthorized login attempt for user {payload.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password. Please check your credentials and try again."
                )
            elif response.status_code == 422:
                # Email not confirmed or account issues
                if "email" in error_detail.lower() and ("confirm" in error_detail.lower() or "verify" in error_detail.lower()):
                    logger.warning(f"Unverified email login attempt: {payload.email}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Please verify your email address before logging in. Check your inbox for a verification code."
                    )
                else:
                    logger.warning(f"Account issue for user {payload.email}: {error_detail}")
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="There is an issue with your account. Please contact support if this persists."
                    )
            elif response.status_code == 429:
                # Too many requests
                logger.warning(f"Rate limited login attempt for user {payload.email}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many login attempts. Please wait a moment before trying again."
                )
            else:
                # Generic error for other status codes
                logger.warning(f"Login failed for user {payload.email}: {error_detail}")
                raise HTTPException(
                    status_code=response.status_code, 
                    detail="Login failed. Please try again or contact support if this persists."
                )

        fcm_token = payload.fcm_token
        if fcm_token:
            await user_service.update_fcm_token(
                user_id=response.json().get("user", {}).get("id"), fcm_token=fcm_token
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
            error_code = None
            
            try:
                if "error_code" in response_data:
                    error_code = response_data["error_code"]
                if "msg" in response_data:
                    error_detail = response_data["msg"]
                elif "message" in response_data:
                    error_detail = response_data["message"]
            except Exception:
                pass

            # Handle specific error cases with user-friendly messages
            if error_code == "user_already_exists" or "already registered" in error_detail.lower():
                logger.warning(f"User already exists: {payload.email}")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email address already exists. Please try logging in instead."
                )
            elif error_code == "signup_disabled":
                logger.warning(f"Signup disabled for: {payload.email}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account registration is currently disabled."
                )
            elif "email" in error_detail.lower() and "invalid" in error_detail.lower():
                logger.warning(f"Invalid email for signup: {payload.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please provide a valid email address."
                )
            elif "password" in error_detail.lower():
                logger.warning(f"Password validation failed for: {payload.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password does not meet requirements. Please ensure it's at least 6 characters long."
                )
            else:
                logger.warning(f"Signup failed for user {payload.email}: {error_detail}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Registration failed: {error_detail}"
                )
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

        # Generate and send email verification
        try:
            otp_code = await user_service.generate_email_verification_otp(user_id, payload.email)
            await user_service.send_verification_email(
                email=payload.email,
                otp_code=otp_code,
                user_name=payload.display_name
            )
            logger.info(f"Verification email sent to {payload.email}")
        except Exception as e:
            logger.warning(f"Failed to send verification email to {payload.email}: {str(e)}")

        logger.info(f"User {payload.email} registered successfully")
        return SignUpResponse(
            message="User registered successfully. Please check your email for a verification code.",
            user=UserMetadata(id=user_id, email=payload.email),
            session=response_data.get("session", {}),
        )

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
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header is missing"
            )
        token = auth_header.split(" ")[1]

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
            template_name="otp.html",  
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
        return VerifyOtpResponse(message="OTP verified.", session_token=session_token)
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
    description="Reset the user's password using OTP and session token.",
)
async def reset_password(request: ResetPasswordRequest) -> Dict:
    """Reset the user's password using OTP and session token."""
    try:
        logger.info(f"Password reset requested for {request.email}")

        # Validate session token
        session_token_entry = await user_service.get_session_token(request.email)
        if not session_token_entry or session_token_entry["token"] != request.session_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session token.")

        # Update the password
        await user_service.update_password(request.email, request.password)

        # Clean up: invalidate session token and OTP
        await user_service.invalidate_session_token(request.email)
        await user_service.invalidate_otp(request.email)

        logger.info(f"Password reset successfully for {request.email}")
        return {"message": "Password reset successfully."}
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"Error resetting password for {request.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request.",
        )


@router.post(
    "/verify-email",
    status_code=status.HTTP_200_OK,
    summary="Verify email address",
    description="Verify user's email address with OTP code.",
)
async def verify_email(request: VerifyEmailRequest) -> VerifyEmailResponse:
    """Verify the user's email address using OTP."""
    try:
        logger.info(f"Email verification requested for {request.email}")

        # Verify email with OTP
        is_verified = await user_service.verify_email_with_otp(request.email, request.otp)
        
        if is_verified:
            return VerifyEmailResponse(
                message="Email verified successfully",
                verified=True
            )
        else:
            return VerifyEmailResponse(
                message="Invalid or expired verification code",
                verified=False
            )

    except Exception as e:
        logger.error(f"Email verification error for {request.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during email verification",
        )


@router.post(
    "/resend-verification",
    status_code=status.HTTP_200_OK,
    summary="Resend verification email",
    description="Resend email verification code to user.",
)
async def resend_verification(request: ResendVerificationRequest) -> ResendVerificationResponse:
    """Resend email verification code to the user."""
    try:
        logger.info(f"Resend verification requested for {request.email}")

        # Check if user exists and is not already verified
        user = await user_service.get_user_by_email(request.email)
        if not user:
            return ResendVerificationResponse(
                message="If an account with this email exists and is unverified, a new verification code has been sent."
            )
        
        if user.get("email_verified", False):
            return ResendVerificationResponse(
                message="This email address is already verified."
            )
        
        # Generate and send new OTP
        otp_code = await user_service.generate_email_verification_otp(user["id"], request.email)
        await user_service.send_verification_email(
            email=request.email,
            otp_code=otp_code,
            user_name=user.get("display_name")
        )
        
        logger.info(f"Verification email resent to {request.email}")
        return ResendVerificationResponse(
            message="A new verification code has been sent to your email address."
        )

    except Exception as e:
        logger.error(f"Error resending verification for {request.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while resending verification email",
        )


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Exchange a refresh token for new access and refresh tokens.",
    response_model=RefreshTokenResponse,
)
async def refresh_token(request: RefreshTokenRequest) -> RefreshTokenResponse:
    """Refresh the user's access token using their refresh token."""
    try:
        logger.info("Token refresh requested")

        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.error("Supabase configuration is missing")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service configuration error",
            )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                    "Content-Type": "application/json",
                },
                json={"refresh_token": request.refresh_token},
            )

        if response.status_code != 200:
            error_detail = "Token refresh failed"
            try:
                error_data = response.json()
                if "error" in error_data and "message" in error_data:
                    error_detail = error_data["message"]
            except Exception:
                pass

            logger.warning(f"Token refresh failed: {error_detail}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid or expired refresh token"
            )

        refresh_data = response.json()
        logger.info("Token refresh successful")
        
        return RefreshTokenResponse(
            access_token=refresh_data["access_token"],
            refresh_token=refresh_data["refresh_token"],
            expires_in=refresh_data["expires_in"],
            expires_at=refresh_data["expires_at"],
            user=UserMetadata(
                id=refresh_data["user"]["id"],
                email=refresh_data["user"]["email"]
            )
        )

    except HTTPException:
        raise
    except httpx.RequestError as e:
        logger.error(f"Error communicating with Supabase: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error communicating with authentication service",
        )
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during token refresh",
        )
