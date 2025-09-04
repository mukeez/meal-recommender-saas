import logging
from fastapi import APIRouter, Depends, Request, HTTPException, status, Header, Query
from datetime import datetime

from app.api.auth_guard import auth_guard
from app.models.billing import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    SubscriptionStatus,
    SubscriptionDetails,
    SubscriptionReactivationRequest,
    SubscriptionReactivationResponse,
    SetupIntentResponse,
    BillingPortalResponse,
    PublishableKey,
    SubscriptionCancellationRequest,
)
from typing import Dict, Any, Optional
from app.services.stripe_service import stripe_service, StripeServiceError
from app.services.mail_service import mail_service
from app.services.user_service import user_service
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/stripe-config",
    status_code=status.HTTP_200_OK,
    response_model=PublishableKey,
    summary="Retrieve stripe publishable key",
    description="Retrieve stripe publishable key",
)
async def get_stripe_config(user=Depends(auth_guard)) -> PublishableKey:
    try:
        if not settings.STRIPE_PUBLISHABLE_KEY:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Publishable key does not exist",
            )
        return PublishableKey(publishable_key=settings.STRIPE_PUBLISHABLE_KEY)
    except HTTPException as e:
        raise
    except Exception as e:
        logger.info(
            f"An unexpected error occured while retrieving publishable key: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occured"
        )


@router.post(
    "/checkout",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Create Stripe checkout session",
    description="Create a Stripe checkout session for subscription with a 7-day free trial",
)
async def create_checkout_session(
    request: CheckoutSessionRequest, user=Depends(auth_guard)
) -> CheckoutSessionResponse:
    try:
        if request.user_id != user.get("id"):
            logger.warning(f"User ID mismatch: {request.user_id} vs {user.get('sub')}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User ID in request does not match authenticated user",
            )

        checkout_session = await stripe_service.create_checkout_session(
            email=request.email, user_id=request.user_id, plan=request.plan
        )

        return checkout_session

    except HTTPException as e:
        raise
    except StripeServiceError as e:
        logger.error(f"Stripe service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating checkout session: {str(e)}",
        )

    except Exception as e:
        logger.error(f"Unexpected error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Process RevenueCat webhook events",
    description="Process RevenueCat webhook events for subscription management",
)
async def process_billing_webhook(request: Request) -> dict:
    import json
    from datetime import timedelta
    
    event_id = None
    user_id = None
    event_type = None
    
    try:
        payload = await request.body()
        
        raw_event = json.loads(payload)
        event = raw_event.get("event")
        
        if not event:
            logger.warning("Webhook payload missing 'event' field")
            return {"status": "error", "message": "Invalid webhook payload"}

        event_id = event.get("id")
        event_type = event.get("type")
        user_id = event.get("app_user_id")
        
        if event_type == "INITIAL_PURCHASE":
            purchased_at_ms = event.get("purchased_at_ms")
            if purchased_at_ms and user_id:
                try:
                    purchased_at = datetime.fromtimestamp(purchased_at_ms / 1000)
                    trial_end_date = purchased_at + timedelta(days=6)
                    await user_service.update_trial_end_date(user_id, str(trial_end_date))
                    logger.info(f"Updated trial end date for user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to update trial end date for user {user_id}: {str(e)}")
            else:
                logger.warning(f"Missing required fields in INITIAL_PURCHASE event: purchased_at_ms={purchased_at_ms}, user_id={user_id}")

            return {"status": "success", "message": f"Event received: {event_type}"}

        logger.info(f"Unhandled event type: {event_type}")
        return {"status": "success", "message": f"Event received: {event_type}"}

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook payload: {str(e)}")
        return {"status": "error", "message": "Invalid JSON payload"}
    except Exception as e:
        logger.error(
            f"Unexpected error processing webhook - event_id: {event_id}, event_type: {event_type}, user_id: {user_id}, error: {str(e)}"
        )
        # Return 200 to prevent unnecessary retries for unexpected errors
        return {"status": "error", "message": "An unexpected error occurred"}


@router.delete(
    "/cancel",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionStatus,
    summary="Cancel a Stripe subscription",
    description="Cancels the user's Stripe subscription either immediately or at the end of the current billing period.",
)
async def cancel_subscription(
    request: SubscriptionCancellationRequest,
    user=Depends(auth_guard),
) -> SubscriptionStatus:
    """
    Cancel a Stripe subscription by its ID.

    - **subscription_id**: The ID of the subscription to cancel.
    - **cancel_at_period_end**: If True, the subscription remains active until the current billing period ends. If False, it is cancelled immediately.
    """
    try:
        user_id = user.get("id")

        # Proceed with cancellation
        sub = await stripe_service.cancel_user_subscription(
            subscription_id=request.subscription_id,
            cancel_at_period_end=request.cancel_at_period_end,
        )

        return SubscriptionStatus(
            status=sub.status,
            subscription_id=sub.id,
            cancel_at_period_end=sub.cancel_at_period_end,
        )

    except StripeServiceError as e:
        logger.error(
            f"Stripe service error cancelling subscription {request.subscription_id} for user {user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling subscription: {str(e)}",
        )
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error cancelling subscription {request.subscription_id} for user {user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while cancelling the subscription.",
        )


@router.post(
    "/create-setup-intent",
    status_code=status.HTTP_200_OK,
    response_model=SetupIntentResponse,
    summary="Create Stripe Setup Intent",
    description="Create stripe setup intent to save user payment method for future transactions",
)
async def create_setup_intent(
    request: CheckoutSessionRequest, user=Depends(auth_guard)
) -> SetupIntentResponse:
    """
    Creates a SetupIntent to collect payment method for a customer.
    """
    user_id = user.get("id")

    if request.user_id != user_id:
        logger.warning(f"User ID mismatch: {request.user_id} vs {user.get('sub')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID in request does not match authenticated user",
        )

    try:
        # Check if user already has an active subscription
        has_subscription = await stripe_service.has_active_subscription(user_id=user_id)
        if has_subscription:
            logger.warning(f"User {user_id} already has an active subscription")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have an active subscription. Please manage your existing subscription instead.",
            )

        # retrieve stripe customer
        customer_id = await stripe_service.get_stripe_customer(user_id=user_id)

        # create stripe customer
        if not customer_id:
            customer_id = await stripe_service.create_stripe_customer(
                user_id=user_id, email=request.email
            )

        await stripe_service.update_stripe_user_subscription(
            customer=customer_id,
            subscription_data={"is_pro": True, "plan": request.plan}
        )


        # create ephemeral key for client side
        ephemeral_key = await stripe_service.create_ephemeral_key(
            user_id=user_id, customer_id=customer_id
        )

        # create sripe setup intent
        setup_intent_key = await stripe_service.create_setup_intent(
            user_id=user_id, customer_id=customer_id, plan=request.plan
        )
        return SetupIntentResponse(
            client_secret=setup_intent_key,
            ephemeral_key=ephemeral_key,
            customer_id=customer_id,
            publishable_key=settings.STRIPE_PUBLISHABLE_KEY or ""
        )

    except HTTPException as e:
        raise
    except Exception as e:
        logger.info(
            f"An unexpected error occured while creating setup intent: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Failed to create setup intent")


@router.post(
    "/create-customer-portal-session",
    status_code=status.HTTP_200_OK,
    response_model=BillingPortalResponse,
    summary="Stripe billing portal session",
    description="Create stripe billing portal session for customer",
)
async def create_customer_portal_session(
    request: Request, user=Depends(auth_guard)
) -> BillingPortalResponse:
    user_id = user.get("id")

    customer_id = await stripe_service.get_stripe_customer(user_id=user_id)

    if not customer_id:
        raise HTTPException(status_code=400, detail="Customer not found.")

    try:
        portal_url = await stripe_service.create_customer_billing_portal(
            user_id=user_id, customer_id=customer_id
        )
        return BillingPortalResponse(url=portal_url)
    except Exception as e:
        logger.info(
            f"An unexpected error occured while creating billing portal session for user: {user_id} with error: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to create billing portal session"
        )


@router.get(
    "/subscription-details",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionDetails,
    summary="Get detailed subscription information",
    description="Get comprehensive subscription details including plan, billing cycle, next billing date, and pricing information",
)
async def get_subscription_details(
    user=Depends(auth_guard)
) -> SubscriptionDetails:
    """
    Get detailed subscription information including plan details and billing information.
    
    This endpoint provides comprehensive subscription information including:
    - Plan type (monthly/yearly)
    - Subscription amount and currency
    - Billing interval and next billing date
    - Current period dates
    - Trial information if applicable
    - Cancellation status
    """
    try:
        user_id = user.get("id")
        
        # Get detailed subscription information from Stripe
        subscription_details = await stripe_service.get_subscription_details(user_id)
        
        return SubscriptionDetails(**subscription_details)
        
    except StripeServiceError as e:
        logger.error(f"Stripe service error getting subscription details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving subscription details"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting subscription details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.post(
    "/reactivate-subscription",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionReactivationResponse,
    summary="Reactivate a subscription",
    description="Reactivate a subscription that was set to cancel at the end of the billing period",
)
async def reactivate_subscription(
    request: SubscriptionReactivationRequest, user=Depends(auth_guard)
) -> SubscriptionReactivationResponse:
    """
    Reactivate a subscription that was set to cancel at period end.
    
    This endpoint allows users to reactivate their subscription if:
    - The subscription exists and is currently active
    - It was set to cancel at the end of the current billing period
    - The current billing period has not yet ended
    
    The subscription will continue with its normal billing cycle after reactivation.
    """
    try:
        user_id = user.get("id")
        # Reactivate the subscription using the ID from the request
        subscription = await stripe_service.reactivate_user_subscription(
            user_id=user_id,
            subscription_id=request.subscription_id
        )

        return SubscriptionReactivationResponse(
            success=True,
            message="Subscription successfully reactivated. Your subscription will continue with its normal billing cycle.",
            subscription_id=subscription.id,
            status=subscription.status,
            cancel_at_period_end=subscription.cancel_at_period_end,
        )

    except StripeServiceError as e:
        logger.error(
            f"Stripe service error reactivating subscription {request.subscription_id}: {str(e)}"
        )

        # Return specific error messages for common scenarios
        error_message = str(e)
        if "No subscription found" in error_message:
            status_code = status.HTTP_404_NOT_FOUND
        elif "not set to cancel" in error_message:
            status_code = status.HTTP_400_BAD_REQUEST
        elif (
            "cannot be reactivated" in error_message
            or "period has already ended" in error_message
        ):
            status_code = status.HTTP_400_BAD_REQUEST
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_message = "Error reactivating subscription"

        raise HTTPException(status_code=status_code, detail=error_message)
    except Exception as e:
        logger.error(
            f"Unexpected error reactivating subscription {request.subscription_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )
