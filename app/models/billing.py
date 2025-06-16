from typing import Optional
from typing_extensions import Annotated
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from app.core.config import settings

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
    trial_end_date : Annotated[Optional[str], Field(None, description="end date for stripe trial period")]

    @field_validator("subscription_start", "subscription_end", "trial_end_date", mode="before")
    @classmethod
    def convert_to_iso(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class SetupIntentResponse(BaseModel):
    client_secret : Annotated[str, Field(..., description="client secret for setup intent")]
    ephemeral_key : Annotated[str, Field(..., description="ephemeral key associated with a stripe customer to be used on the client side")]
    customer_id : Annotated[str, Field(..., description="stripe customer id")]
    publishable_key : Annotated[str, Field(settings.STRIPE_PUBLISHABLE_KEY, description="stripe publishable key to be used on the client side")]

class BillingPortalResponse(BaseModel):
    url: str = Field(..., description="URL to redirect to Stripe customer billing portal")


class PublishableKey(BaseModel):
    publishable_key : Annotated[str, Field(settings.STRIPE_PUBLISHABLE_KEY, description="stripe publishable key to be used on the client side")]