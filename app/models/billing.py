from typing import Literal, Optional
from typing_extensions import Annotated
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from app.core.config import settings

class CheckoutSessionRequest(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    user_id: str = Field(..., description="User ID for subscription metadata")
    plan: Literal["monthly", "yearly"] = Field(..., description="Plan to subscribe to")
    


class CheckoutSessionResponse(BaseModel):
    checkout_url: str = Field(..., description="URL to redirect to Stripe checkout")
    session_id: str = Field(..., description="Stripe checkout session ID")


class SubscriptionStatus(BaseModel):
    status: str = Field(..., description="status of the subscriiption")
    subscription_id: Optional[str] = Field(None, description="Stripe subscription ID")
    cancel_at_period_end: Optional[bool] = Field(None, description="Whether subscription cancels at period end")


class SubscriptionDetails(BaseModel):
    """Detailed subscription information including plan and billing details."""
    has_subscription: bool = Field(..., description="Whether user has a subscription")
    subscription_id: Optional[str] = Field(None, description="Stripe subscription ID")
    status: Optional[str] = Field(None, description="Subscription status (active, trialing, past_due, etc.)")
    plan: Optional[Literal["monthly", "yearly"]] = Field(None, description="Subscription plan type")
    plan_name: Optional[str] = Field(None, description="Human-readable plan name")
    amount: Optional[float] = Field(None, description="Subscription amount")
    currency: Optional[str] = Field(None, description="Subscription currency")
    billing_interval: Optional[str] = Field(None, description="Billing interval (month, year)")
    current_period_start: Optional[datetime] = Field(None, description="Current billing period start date")
    current_period_end: Optional[datetime] = Field(None, description="Current billing period end date")
    next_billing_date: Optional[datetime] = Field(None, description="Next billing date")
    trial_end: Optional[datetime] = Field(None, description="Trial end date if applicable")
    cancel_at_period_end: Optional[bool] = Field(None, description="Whether subscription cancels at period end")
    created: Optional[datetime] = Field(None, description="Subscription creation date")


class SubscriptionUpdate(BaseModel):
    is_pro : Annotated[Optional[bool], Field(None, description="whether the user is subscribe or not")]
    stripe_subscription_id : Annotated[Optional[str], Field(None, description="stripe subscription id")]
    subscription_start : Annotated[Optional[str], Field(None, description="start date for stripe subscription")]
    subscription_end : Annotated[Optional[str], Field(None, description="end date fot stripe subscription")]
    trial_end_date : Annotated[Optional[str], Field(None, description="end date for stripe trial period")]
    plan : Annotated[Optional[Literal["monthly", "yearly"]], Field(None, description="plan to subscribe to")]

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


class SubscriptionReactivationResponse(BaseModel):
    """Response model for subscription reactivation."""
    success: bool = Field(..., description="Whether reactivation was successful")
    message: str = Field(..., description="Success or error message")
    subscription_id: str = Field(..., description="Stripe subscription ID")
    status: str = Field(..., description="Updated subscription status")
    cancel_at_period_end: bool = Field(..., description="Whether subscription will cancel at period end")


class PublishableKey(BaseModel):
    publishable_key: str