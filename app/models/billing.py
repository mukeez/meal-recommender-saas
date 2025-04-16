from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class CheckoutSessionRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    user_id: str = Field(..., description="User ID for subscription metadata")


class CheckoutSessionResponse(BaseModel):
    checkout_url: str = Field(..., description="URL to redirect to Stripe checkout")
    session_id: str = Field(..., description="Stripe checkout session ID")


class SubscriptionStatus(BaseModel):
    is_active: bool = Field(..., description="Whether the subscription is active")
    subscription_id: Optional[str] = Field(None, description="Stripe subscription ID")
    current_period_end: Optional[int] = Field(None, description="Timestamp when current period ends")
    cancel_at_period_end: Optional[bool] = Field(None, description="Whether subscription cancels at period end")