"""Data models for the auth API.

This module contains Pydantic models that define the structure of request and
response data for the auth API.
"""

from typing import Optional, Dict
from typing_extensions import Annotated
from pydantic import BaseModel, Field, EmailStr, field_validator

class LoginRequest(BaseModel):
    """Login request model.

    Attributes:
        email: User's email address
        password: User's password
        fcm_token: Optional Firebase Cloud Messaging token for push notifications
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")
    fcm_token: Optional[str] = Field(
        None, description="Firebase Cloud Messaging token for push notifications"
    )


class UserMetadata(BaseModel):
    """User metadata model

    Attributes:
        id: uniquer identifier(ID) of user
        email: verified user email
    """
    id: Annotated[str, Field(..., description="unique identifier(ID) of user")]
    email : Annotated[str, Field(..., description="verified user email")]


class LoginResponse(BaseModel):
    """Login response model

    Attributes:
        access_token: access_token
        refresh_token: refresh_token
        expires_in: expiration value(secs) for access token
        expires_at: timestamp value for when access token expires
        user: user metadata
    """
    access_token : Annotated[str, Field(..., description="access token")]
    refresh_token: Annotated[str, Field(..., description="refresh token")]
    expires_in : Annotated[int, Field(..., description="expiration value(secs) for access token")]
    expires_at: Annotated[int, Field(..., description="timestamp value for when access token expires")]
    user: Annotated[UserMetadata, Field(..., alias="user", description="user metadata")]
        

class SignUpResponse(BaseModel):
    """Signup response model

    Attributes:
        message: success response message
        user: user metadata
        session: supabase session data
    """
    message: Annotated[str, Field(..., description="success response message")]
    user: Annotated[UserMetadata, Field(..., description="user metadata")]
    session: Annotated[Dict, Field(..., description="supabase session data")]

class SignupRequest(BaseModel):
    """Signup request model with basic validation.

    Attributes:
        email: User's email address
        password: User's password
        display_name: User's display name (optional)
        fcm_token: Optional Firebase Cloud Messaging token for push notifications
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=6, description="User's password (min 6 characters)")
    display_name: Optional[str] = Field(None, description="User's display name")
    fcm_token: Optional[str] = Field(
        None, description="Firebase Cloud Messaging token for push notifications"
    )

    @field_validator('password')
    def validate_password_length(cls, value):
        """Validate password meets minimum length requirement."""
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return value
    

class ResetPasswordRequest(BaseModel):
    """Reset password request model.

    Attributes:
        email: User's email address
        otp: OTP for verification
        password: New password
        session_token: Session token from OTP verification
    """
    email: EmailStr = Field(..., description="User's email address")
    otp: str = Field(..., description="OTP for verification")
    password: str = Field(..., min_length=6, description="New password (min 6 characters)")
    session_token: str = Field(..., description="Session token from OTP verification")

    @field_validator('password')
    def validate_password_length(cls, value):
        """Validate password meets minimum length requirement."""
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return value


class VerifyOtpResponse(BaseModel):
    """
    VerifyOtpResponse represents the response model for verifying an OTP.

    Attributes:
        message (str): A message indicating the result of the OTP verification.
        session_token (str): A token representing the session associated with the OTP verification.
    """
    message: Annotated[str, Field(..., description="indicates the result of the OTP verification")]
    session_token: Annotated[str, Field(..., description="otp verification session")]


class VerifyOtpRequest(BaseModel):
    """
    VerifyOtpRequest represents the request model for verifying a one-time password.
    
    This model is used when a user submits an OTP code they received via email
    during the password reset flow to verify their identity.
    
    Attributes:
        email (EmailStr): The email address associated with the OTP.
        otp (str): The one-time password code to verify.
    """
    email: Annotated[EmailStr, Field(..., description="User's email address for verification")]
    otp: Annotated[str, Field(..., description="One-time password code to verify")]


class VerifyEmailRequest(BaseModel):
    """Email verification request model.

    Attributes:
        email: User's email address
        otp: OTP code for verification
    """
    email: EmailStr = Field(..., description="User's email address")
    otp: str = Field(..., description="6-digit OTP code for verification")


class VerifyEmailResponse(BaseModel):
    """Email verification response model.

    Attributes:
        message: Success message
        verified: Whether verification was successful
    """
    message: str = Field(..., description="Response message")
    verified: bool = Field(..., description="Whether email was verified successfully")


class ResendVerificationRequest(BaseModel):
    """Resend verification email request model.

    Attributes:
        email: User's email address
    """
    email: EmailStr = Field(..., description="User's email address")


class ResendVerificationResponse(BaseModel):
    """Resend verification email response model.

    Attributes:
        message: Success message
    """
    message: str = Field(..., description="Success message")


class RefreshTokenRequest(BaseModel):
    """Refresh token request model.

    Attributes:
        refresh_token: The refresh token to exchange for new tokens
    """
    refresh_token: str = Field(..., description="Refresh token")


class RefreshTokenResponse(BaseModel):
    """Refresh token response model.

    Attributes:
        access_token: New access token
        refresh_token: New refresh token  
        expires_in: Expiration time in seconds for access token
        expires_at: Timestamp when access token expires
        user: User metadata
    """
    access_token: str = Field(..., description="New access token")
    refresh_token: str = Field(..., description="New refresh token")
    expires_in: int = Field(..., description="Expiration time in seconds for access token")
    expires_at: int = Field(..., description="Timestamp when access token expires")
    user: UserMetadata = Field(..., description="User metadata")

