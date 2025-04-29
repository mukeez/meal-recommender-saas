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