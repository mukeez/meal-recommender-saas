import logging
from fastapi import APIRouter, Depends, Request, HTTPException, status, Header, Query
from typing import Optional
from datetime import datetime

from app.api.auth_guard import auth_guard
from app.models.billing import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    SubscriptionUpdate,
    SubscriptionStatus,
    SetupIntentResponse,
    BillingPortalResponse,
    PublishableKey,
)
from app.services.stripe_service import stripe_service, StripeServiceError
from app.services.mail_service import mail_service
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
        return {"publishable_key": settings.STRIPE_PUBLISHABLE_KEY}
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
    description="Create a Stripe checkout session for subscription with a 3-day free trial",
)
async def create_checkout_session(
    request: CheckoutSessionRequest, user=Depends(auth_guard)
) -> CheckoutSessionResponse:
    try:
        if request.user_id != user.get("sub"):
            logger.warning(f"User ID mismatch: {request.user_id} vs {user.get('sub')}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User ID in request does not match authenticated user",
            )

        checkout_session = await stripe_service.create_checkout_session(
            email=request.email, user_id=request.user_id
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
    summary="Process Stripe webhook events",
    description="Process Stripe webhook events for subscription management",
)
async def stripe_webhook(
    request: Request, stripe_signature: str = Header(..., alias="Stripe-Signature")
) -> dict:
    try:
        payload = await request.body()

        event = stripe_service.verify_webhook_signature(payload, stripe_signature)

        if event["type"] == "setup_intent.succeeded":
            session = event["data"]["object"]
            payment_method = session["payment_method"]
            customer_id = session["customer"]
            # create subscription for user
            await stripe_service.create_subscription(
                customer_id=customer_id,
                payment_method_id=payment_method,
            )
            
            # Get customer email and send welcome email
            customer_email = await stripe_service.get_customer_email(customer_id)
            if customer_email:
                await mail_service.send_email(
                    recipient=customer_email,
                    subject="Welcome to Macro Meals Pro!",
                    template_name="subscription_created.html",
                    context={
                        "subscription_type": "Macro Meals Pro",
                        "trial_days": 3,
                    }
                )
            
            logger.info(f"Subscription created for user: {customer_id}")
            return {
                "status": "success",
                "message": "Setup intent and subscription creation completed succesfully",
            }

        elif event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = await stripe_service.handle_checkout_completed(session)
            
            # Get customer email from session
            customer_email = session.get("customer_details", {}).get("email")
            if customer_email:
                await mail_service.send_email(
                    recipient=customer_email,
                    subject="Welcome to Macro Meals Pro!",
                    template_name="subscription_created.html",
                    context={
                        "subscription_type": "Macro Meals Pro",
                        "trial_days": 3,
                    }
                )
                
            logger.info(f"Checkout completed for user: {user_id}")
            return {"status": "success", "message": "Checkout completed successfully"}
        
        elif event["type"] == "customer.subscription.created":
            from supabase import create_client

            session = event["data"]["object"]
            customer_id = session["customer"]
            session_trial_end_date = session["trial_end"]
            trial_end_date = datetime.fromtimestamp(session_trial_end_date).date()

            client = create_client(
                settings.SUPABASE_SERVICE_ROLE_KEY, settings.SUPABASE_URL
            )
            client.table("user_profiles").update({"trial_end_date": trial_end_date}).eq(
                "stripe_customer_id", customer_id
            ).execute()
            logger.info(
                f"Subscription created for user: {customer_id} with trial end date: {trial_end_date}"
            )
            return {
                "status": "success",
                "message": "Subscription created successfully",
            }

        elif event["type"] == "customer.subscription.deleted":
            session = event["data"]["object"]
            customer_id = session["customer"]
            await stripe_service.update_stripe_user_subscription(
                customer=customer_id,
                subscription_data=SubscriptionUpdate(is_pro=False),
            )
            
            # Get customer email and send cancellation email
            customer_email = await stripe_service.get_customer_email(customer_id)
            if customer_email:
                await mail_service.send_email(
                    recipient=customer_email,
                    subject="Your Macro Meals Pro Subscription",
                    template_name="subscription_cancelled.html",
                    context={
                        "subscription_type": "Macro Meals Pro",
                        "cancellation_date": datetime.now().strftime("%B %d, %Y")
                    }
                )
            
            return {
                "status": "success",
                "message": "Subscription cancelled successfully",
            }

        # update subscription start and end dates - no email for renewals as requested
        elif event["type"] == "invoice.paid":
            session = event["data"]["object"]
            customer = session["customer"]
            subscription_start = datetime.fromtimestamp(
                session["lines"]["data"][0]["period"]["start"]
            ).isoformat()
            subscription_end = datetime.fromtimestamp(
                session["lines"]["data"][0]["period"]["end"]
            ).isoformat()
            subscription_data = SubscriptionUpdate(
                subscription_start=subscription_start,
                subscription_end=subscription_end,
                is_pro=True,
            )
            await stripe_service.update_stripe_user_subscription(
                customer=customer, subscription_data=subscription_data
            )
            return {"status": "success", "message": "Subscription renewed"}

        return {"status": "success", "message": f"Event received: {event['type']}"}

    except StripeServiceError as e:
        logger.error(f"Stripe webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook processing error: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.delete(
    "/cancel",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionStatus,
    summary="Cancel a Stripe subscription",
)
async def cancel_subscription(
    cancel_at_period_end: bool = Query(
        True,
        description="Set to True to cancel at period request: CheckoutSessionRequest",
    ),
    user=Depends(auth_guard),
) -> SubscriptionStatus:
    """
    Cancel a Stripe subscription.

    - **cancel_at_period_end**: if True, the subscription remains active until period end.
    """
    try:
        user_id = user.get("sub")
        if cancel_at_period_end:
            # Schedule cancellation at period end
            sub = await stripe_service.cancel_user_subscription(
                user_id=user_id, cancel_at_period_end=True
            )
        else:
            # Cancel immediately
            sub = await stripe_service.cancel_user_subscription(
                user_id=user_id, cancel_at_period_end=False
            )

    except StripeServiceError as e:
        logger.error(f"Stripe service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling subscription",
        )
    except Exception:
        logger.error(f"Unexpected error cancelling subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )

    return sub


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
    user_id = user["sub"]

    if request.user_id != user_id:
        logger.warning(f"User ID mismatch: {request.user_id} vs {user.get('sub')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID in request does not match authenticated user",
        )

    try:
        # retrieve stripe customer
        customer_id = await stripe_service.get_stripe_customer(user_id=user_id)

        # create stripe customer
        if not customer_id:
            customer_id = await stripe_service.create_stripe_customer(
                user_id=user_id, email=request.email
            )

        # create ephemeral key for client side
        ephemeral_key = await stripe_service.create_ephemeral_key(
            user_id=user_id, customer_id=customer_id
        )

        # create sripe setup intent
        setup_intent_key = await stripe_service.create_setup_intent(
            user_id=user_id, customer_id=customer_id
        )
        return {
            "client_secret": setup_intent_key,
            "ephemeral_key": ephemeral_key,
            "customer_id": customer_id,
        }

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
    user_id = user.get("sub")

    customer_id = await stripe_service.get_stripe_customer(user_id=user_id)

    if not customer_id:
        raise HTTPException(status_code=400, detail="Customer not found.")

    try:
        portal_url = await stripe_service.create_customer_billing_portal(
            user_id=user_id, customer_id=customer_id
        )
        return portal_url
    except Exception as e:
        logger.info(
            f"An unexpected error occured while creating billing portal session for user: {user_id} with error: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to create billing portal session"
        )
