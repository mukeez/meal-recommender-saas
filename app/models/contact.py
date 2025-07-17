"""Contact form models for the meal recommendation API.

This module contains the Pydantic models for contact form functionality.
"""

from typing import Optional
from typing_extensions import Annotated
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class ContactFormRequest(BaseModel):
    """Request model for contact form submissions.

    Attributes:
        name: Full name of the person contacting support
        email: Email address for response
        message: The message or inquiry from the client
        subject: Optional subject line for the inquiry
    """
    name: Annotated[str, Field(..., min_length=1, max_length=100, description="Full name of the person contacting support")]
    email: Annotated[EmailStr, Field(..., description="Email address for response")]
    message: Annotated[str, Field(..., min_length=10, max_length=2000, description="The message or inquiry from the client")]
    subject: Annotated[Optional[str], Field(None, max_length=200, description="Optional subject line for the inquiry")]

    model_config = ConfigDict(populate_by_name=True)


class ContactFormResponse(BaseModel):
    """Response model for contact form submissions.

    Attributes:
        success: Whether the contact form was submitted successfully
        message: Success message for the user
        reference_id: Optional reference ID for tracking the inquiry
    """
    success: bool = Field(..., description="Whether the contact form was submitted successfully")
    message: str = Field(..., description="Success message for the user")
    reference_id: Optional[str] = Field(None, description="Optional reference ID for tracking the inquiry") 