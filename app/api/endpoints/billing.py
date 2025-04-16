import logging
from fastapi import APIRouter, Depends, Request, HTTPException, status, Header
from typing import Optional

from app.api.auth_guard import auth_guard
from app.models.billing import CheckoutSessionRequest, CheckoutSessionResponse
from app.services.stripe_service import stripe_service, StripeServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/checkout",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Create Stripe checkout session",
    description="Create a Stripe checkout session for subscription with a 3-day free trial"
)
async def create_checkout_session(
        request: CheckoutSessionRequest,
        user=Depends(auth_guard)
) -> CheckoutSessionResponse:
    try:
        if request.user_id != user.get("sub"):
            logger.warning(f"User ID mismatch: {request.user_id} vs {user.get('sub')}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User ID in request does not match authenticated user"
            )

        checkout_session = await stripe_service.create_checkout_session(
            email=request.email,
            user_id=request.user_id
        )

        return checkout_session

    except StripeServiceError as e:
        logger.error(f"Stripe service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating checkout session: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Process Stripe webhook events",
    description="Process Stripe webhook events for subscription management"
)
async def stripe_webhook(
        request: Request,
        stripe_signature: str = Header(..., alias="Stripe-Signature")
) -> dict:
    try:
        payload = await request.body()

        event = stripe_service.verify_webhook_signature(payload, stripe_signature)

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = await stripe_service.handle_checkout_completed(session)
            logger.info(f"Checkout completed for user: {user_id}")
            return {"status": "success", "message": "Checkout completed successfully"}

        return {"status": "success", "message": f"Event received: {event['type']}"}

    except StripeServiceError as e:
        logger.error(f"Stripe webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook processing error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )