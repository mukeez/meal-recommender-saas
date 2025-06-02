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
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


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
    """
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=6, description="User's password (min 6 characters)")
    display_name: Optional[str] = Field(None, description="User's display name")

    @field_validator('password')
    def validate_password_length(cls, value):
        """Validate password meets minimum length requirement."""
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return value
    

class ResetPasswordRequest(BaseModel):
    """
    ResetPasswordRequest represents the request model for resetting a user's password.
    
    This model is used when a user completes the password reset flow after verifying 
    their identity with an OTP. It contains the user's email, new password, and the 
    session token obtained during OTP verification.
    
    Attributes:
        email (EmailStr): The email address of the user requesting password reset.
        new_password (str): The new password that will replace the user's current password.
        session_token (str): The verification token received after successful OTP validation.
    """
    email: Annotated[EmailStr, Field(..., description="User's email address for password reset")]
    new_password: Annotated[str, Field(..., description="The new password to set for the user account")]
    session_token: Annotated[str, Field(..., description="Session token for password reset verification")]


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

