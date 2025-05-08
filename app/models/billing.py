from typing import Optional
from typing_extensions import Annotated
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime

class CheckoutSessionRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    user_id: str = Field(..., description="User ID for subscription metadata")


class CheckoutSessionResponse(BaseModel):
    checkout_url: str = Field(..., description="URL to redirect to Stripe checkout")
    session_id: str = Field(..., description="Stripe checkout session ID")


class SubscriptionStatus(BaseModel):
    status: str = Field(..., description="status of the subscriiption")
    subscription_id: Optional[str] = Field(None, description="Stripe subscription ID")
    cancel_at_period_end: Optional[bool] = Field(None, description="Whether subscription cancels at period end")


class SubscriptionUpdate(BaseModel):
    is_pro : Annotated[Optional[bool], Field(None, description="whether the user is subscribe or not")]
    stripe_subscription_id : Annotated[Optional[str], Field(None, description="stripe subscription id")]
    subscription_start : Annotated[Optional[str], Field(None, description="start date for stripe subscription")]
    subscription_end : Annotated[Optional[str], Field(None, description="end date fot stripe subscription")]

    @field_validator("subscription_start", "subscription_end", mode="before")
    @classmethod
    def convert_to_iso(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

