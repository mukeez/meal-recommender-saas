import os
import logging
import stripe
from typing import Dict, Any, Optional

from app.core.config import settings
from app.models.billing import CheckoutSessionResponse

logger = logging.getLogger(__name__)


class StripeServiceError(Exception):
    pass


class StripeService:
    def __init__(self):
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        self.price_id = os.getenv("STRIPE_PRICE_ID")

        if not stripe.api_key:
            logger.error("STRIPE_SECRET_KEY environment variable is not set")
            raise ValueError("STRIPE_SECRET_KEY environment variable is not set")

        if not self.webhook_secret:
            logger.warning("STRIPE_WEBHOOK_SECRET environment variable is not set")

        if not self.price_id:
            logger.error("STRIPE_PRICE_ID environment variable is not set")
            raise ValueError("STRIPE_PRICE_ID environment variable is not set")

    async def create_checkout_session(self, email: str, user_id: str) -> CheckoutSessionResponse:
        try:
            logger.info(f"Creating checkout session for user: {user_id}")

            checkout_session = stripe.checkout.Session.create(
                customer_email=email,
                payment_method_types=["card"],
                line_items=[{
                    "price": self.price_id,
                    "quantity": 1
                }],
                mode="subscription",
                subscription_data={
                    "trial_period_days": 3
                },
                metadata={
                    "user_id": user_id
                },
                success_url=f"https://macromealsapp.com/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url="https://macromealsapp.com/cancel"
            )

            logger.info(f"Checkout session created: {checkout_session.id}")

            return CheckoutSessionResponse(
                checkout_url=checkout_session.url,
                session_id=checkout_session.id
            )

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeServiceError(f"Error creating checkout session: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating checkout session: {str(e)}")
            raise StripeServiceError(f"Unexpected error: {str(e)}")

    def verify_webhook_signature(self, payload: bytes, signature: str) -> Dict[str, Any]:
        try:
            logger.info("Verifying webhook signature")

            if not self.webhook_secret:
                logger.error("Webhook secret is not configured")
                raise StripeServiceError("Webhook secret is not configured")

            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=signature,
                secret=self.webhook_secret
            )

            logger.info(f"Webhook verified: {event.id}, type: {event.type}")
            return event

        except ValueError as e:
            logger.error(f"Invalid payload: {str(e)}")
            raise StripeServiceError(f"Invalid payload: {str(e)}")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Signature verification failed: {str(e)}")
            raise StripeServiceError(f"Signature verification failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error verifying webhook: {str(e)}")
            raise StripeServiceError(f"Unexpected error: {str(e)}")

    async def handle_checkout_completed(self, session: Dict[str, Any]) -> str:
        try:
            user_id = session.get("metadata", {}).get("user_id")

            if not user_id:
                logger.error("User ID not found in session metadata")
                raise StripeServiceError("User ID not found in session metadata")

            logger.info(f"Processing completed checkout for user: {user_id}")

            await self.mark_user_as_subscribed(user_id)

            logger.info(f"User {user_id} marked as subscribed")
            return user_id

        except Exception as e:
            logger.error(f"Error handling checkout completed: {str(e)}")
            raise StripeServiceError(f"Error handling checkout completed: {str(e)}")

    async def mark_user_as_subscribed(self, user_id: str) -> None:
        logger.info(f"Marking user {user_id} as subscribed (placeholder function)")
        pass


stripe_service = StripeService()