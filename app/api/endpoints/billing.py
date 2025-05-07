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
)
from app.services.stripe_service import stripe_service, StripeServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


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


        # check for customer id and update user details
        if event["type"] == "customer.created":
            session = event["data"]["object"]
            await stripe_service.handle_stripe_customer_created(session=session)

        elif event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = await stripe_service.handle_checkout_completed(session)
            logger.info(f"Checkout completed for user: {user_id}")
            return {"status": "success", "message": "Checkout completed successfully"}

        elif event["type"] == "customer.subscription.deleted":
            session = event["data"]["object"]
            await stripe_service.update_stripe_user_subscription(
                customer=session["customer"], subscription_data=SubscriptionUpdate(is_pro=False)
            )
            return {
                "status": "success",
                "message": "Subscription cancelled successfully",
            }

        # update subscription start and end dates
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
    response_model=SubscriptionStatus,
    summary="Cancel a Stripe subscription",
    tags=["subscriptions"],
)
async def cancel_subscription(
    cancel_at_period_end: bool = Query(
        True,
        description="Set to True to cancel at period request: CheckoutSessionRequest",
    ),
    user=Depends(auth_guard),
):
    """
    Cancel a Stripe subscription.

    - **subscription_id**: the ID of the subscription to cancel (e.g. 'sub_123').
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
