"""Stripe Service Module
Handles Stripe API interactions for billing, subscriptions and customer management.
"""

import logging
from fastapi import status
from fastapi.exceptions import HTTPException
import os
import stripe
from typing import Dict, Any, List, Optional
import time
from datetime import datetime

from app.models.billing import CheckoutSessionResponse, SubscriptionUpdate
from app.utils.helper_functions import remove_null_values
from app.services.base_database_service import BaseDatabaseService
from app.core.config import settings


logger = logging.getLogger(__name__)


class StripeServiceError(Exception):
    """Custom exception for Stripe service operations."""
    pass


class StripeService:
    """Service for managing Stripe billing and subscriptions."""
    def __init__(self):
        """Initialize with Stripe API credentials and configuration."""
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

    async def create_checkout_session(
        self, email: str, user_id: str
    ) -> CheckoutSessionResponse:
        """Create a Stripe checkout session for subscription.

        Args:
            email: User's email address
            user_id: User's unique identifier

        Returns:
            CheckoutSessionResponse with checkout URL and session ID

        Raises:
            StripeServiceError: On checkout session creation failure
            HTTPException: If user already has payment details
        """
        try:
            logger.info(f"Creating checkout session for user: {user_id}")

            # get stripe customer id if exists
            customer = await self.get_stripe_customer(user_id=user_id)

            params = {
                "payment_method_types": ["card"],
                "line_items": [{"price": self.price_id, "quantity": 1}],
                "mode": "subscription",
                "metadata": {"user_id": user_id},
                "success_url": f"https://macromealsapp.com/success?session_id={{CHECKOUT_SESSION_ID}}",
                "cancel_url": "https://macromealsapp.com/cancel",
            }
            if customer:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Payment details already exist for this user",
                )
            else:
                # add trial period
                params["customer_email"] = email
                params["subscription_data"] = {"trial_period_days": 3}

            checkout_session = stripe.checkout.Session.create(**params)

            logger.info(f"Checkout session created: {checkout_session.id}")

            return CheckoutSessionResponse(
                checkout_url=checkout_session.url, session_id=checkout_session.id
            )

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeServiceError(f"Error creating checkout session: {str(e)}")
        except HTTPException as e:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating checkout session: {str(e)}")
            raise StripeServiceError(f"Unexpected error: {str(e)}")

    def verify_webhook_signature(
        self, payload: bytes, signature: str
    ) -> Dict[str, Any]:
        """Verify Stripe webhook signature.

        Args:
            payload: Raw webhook payload
            signature: Signature header from request

        Returns:
            Verified event data

        Raises:
            StripeServiceError: On signature verification failure
        """
        try:
            logger.info("Verifying webhook signature")

            if not self.webhook_secret:
                logger.error("Webhook secret is not configured")
                raise StripeServiceError("Webhook secret is not configured")

            event = stripe.Webhook.construct_event(
                payload=payload, sig_header=signature, secret=self.webhook_secret
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
        """Handle checkout session completion.

        Args:
            session: Stripe session data containing customer information

        Returns:
            Stripe customer ID

        Raises:
            StripeServiceError: When customer ID not found or update fails
        """
        try:
            # get stripe customer id
            customer = session.get("customer", None)

            if not customer:
                logger.error("customer not found in session")
                raise StripeServiceError("customer not found in session")
            logger.info(f"Processing completed checkout for user: {customer}")

            await self.update_stripe_user_subscription(
                customer, subscription_data=SubscriptionUpdate(is_pro=True)
            )

            logger.info(f"User {customer} marked as subscribed")
            return customer

        except Exception as e:
            logger.error(f"Error handling checkout completed: {str(e)}")
            raise StripeServiceError(f"Error handling checkout completed: {str(e)}")

    async def handle_stripe_customer_created(self, session: Dict[str, Any]) -> None:
        """Handle new Stripe customer creation.

        Updates user profile with Stripe customer and subscription details.

        Args:
            session: Stripe session data with email and customer ID

        Raises:
            StripeServiceError: When customer email missing or DB update fails
        """
        try:
            customer_email = session.get("email", None)
            customer_id = session["id"]

            if not customer_email:
                logger.error("customer not found in session")
                raise StripeServiceError("customer not found in session")

            if not BaseDatabaseService.subclasses:
                raise StripeServiceError("No database service implementation available")

            # get subscription id from customer data
            subscription = await self.get_subscription_with_retry(
                customer_id=customer_id
            )

            # update user data with stripe customer id
            BaseDatabaseService.subclasses[0]().update_data(
                table_name="user_profiles",
                data={
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription["subscription_id"],
                    "subscription_start": subscription["subscription_start"],
                    "subscription_end": subscription["subscription_end"],
                },
                cols={"email": customer_email},
            )

            logger.info(f"Stripe customer id created for: {customer_email}")
        except Exception as e:
            logger.error(f"Error handling stripe customer created: {str(e)}")
            raise StripeServiceError(
                f"Error handling stripe customer created: {str(e)}"
            )

    async def update_stripe_user_subscription(
        self, customer: str, subscription_data: SubscriptionUpdate
    ) -> None:
        """Update user subscription information.

        Args:
            customer: Stripe customer ID
            subscription_data: Subscription details including pro status

        Raises:
            StripeServiceError: When database update fails
        """

        try:
            logger.info(
                f"Marking user with stripe customer id {customer} as subscribed"
            )

            if not BaseDatabaseService.subclasses:
                raise StripeServiceError("No database service implementation available")

            subscription_data_dict = remove_null_values(subscription_data.model_dump())

            # update user's stripe details
            BaseDatabaseService.subclasses[0]().update_data(
                table_name="user_profiles",
                data=subscription_data_dict,
                cols={"stripe_customer_id": customer},
            )

        except Exception as e:
            logger.error(f"Error updating user subscription: {str(e)}")
            raise StripeServiceError(f"Error updating user subscription: {str(e)}")

    async def cancel_user_subscription(
        self, user_id: str, cancel_at_period_end: bool = True
    ) -> stripe.Subscription:
        """Cancel user's Stripe subscription.

        Args:
            user_id: User identifier
            cancel_at_period_end: Whether to cancel at billing period end

        Returns:
            Updated Stripe Subscription object

        Raises:
            StripeServiceError: When subscription not found or cancellation fails
        """
        try:
            logger.info(f"Cancelling subscription for user: {user_id}")
            if not BaseDatabaseService.subclasses:
                raise StripeServiceError("No database service implementation available")

            # fetch stripe subscription id for user if it exists
            response = BaseDatabaseService.subclasses[0]().select_data(
                table_name="user_profiles", cols={"id": user_id}
            )
            if response and isinstance(response, List):
                subscription_id = response[0]["stripe_subscription_id"]
            elif response:
                subscription_id = response

            else:
                subscription_id = None

            if not subscription_id:
                raise StripeServiceError("Subscription id not found for customer")

            data = {"stripe_customer_id": None, "stripe_subscription_id": None}

            if cancel_at_period_end:
                sub = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                )
            else:
                sub = stripe.Subscription.delete(subscription_id)
                data["is_pro"] = False

            BaseDatabaseService.subclasses[0].update_data(
                table_name="user_profiles", data=data, cols={"id": user_id}
            )

            return sub
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeServiceError(f"Error cancelling subscription: {str(e)}")
        except Exception as e:
            logger.error(
                f"Failed to cancel subscription for user: {user_id} with error{str(e)}"
            )
            raise StripeServiceError("Unexpected error while cancelling subscription")

    async def get_subscription_with_retry(
        self, customer_id: str, retries: int = 2, delay: float = 2.0
    ) -> Dict:
        """Get customer subscription with retry logic.

        Args:
            customer_id: Stripe customer ID
            retries: Maximum retry attempts
            delay: Seconds between retries

        Returns:
            Dict with subscription_id, subscription_start and subscription_end

        Raises:
            StripeServiceError: When no active subscriptions found after retries
        """
        for attempt in range(1, retries + 1):
            try:
                customer = stripe.Customer.retrieve(
                    customer_id, expand=["subscriptions.data"]
                )
                subscriptions = customer.subscriptions.data
                if subscriptions:
                    # get first trial subscription
                    trial_subs = [s for s in subscriptions if s["status"] == "trialing"]
                    subscription_id = trial_subs[0]["id"]
                    subscription_start = datetime.fromtimestamp(
                        trial_subs[0]["items"]["data"][0]["current_period_start"]
                    ).isoformat()
                    subscription_end = datetime.fromtimestamp(
                        trial_subs[0]["items"]["data"][0]["current_period_end"]
                    ).isoformat()
                    return {
                        "subscription_id": subscription_id,
                        "subscription_start": subscription_start,
                        "subscription_end": subscription_end,
                    }
                else:
                    raise StripeServiceError(
                        f"No subscriptions found for customer {customer_id}"
                    )
            except (stripe.error.StripeError, StripeServiceError) as e:
                if attempt == retries:
                    raise StripeServiceError(
                        f"Failed to retrieve subscription after {retries} attempts: {e}"
                    )
                time.sleep(delay)

    async def create_stripe_customer(self, user_id: str, email: str) -> str:
        """Create Stripe customer and update user profile.

        Args:
            user_id: Internal user ID
            email: User email address

        Returns:
            New Stripe customer ID

        Raises:
            StripeServiceError: On Stripe API or database errors
        """
        try:
            if not BaseDatabaseService.subclasses:
                raise StripeServiceError("No database service implementation available")
            customer = stripe.Customer.create(
                email=email, metadata={"user_id": user_id}
            )
            # update user's associated stripe customer id
            BaseDatabaseService.subclasses[0]().update_data(
                table_name="user_profiles",
                data={"stripe_customer_id": customer.id},
                cols={"id": user_id},
            )
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeServiceError(f"Error creating stripe customer: {str(e)}")
        except Exception as e:
            logger.error(
                f"Failed to create stripe customer: {user_id} with error: {str(e)}"
            )
            raise StripeServiceError("Unexpected error while creating stripe customer")

    async def get_stripe_customer(self, user_id: str) -> Optional[str]:
        """Get Stripe customer ID for user.

        Args:
            user_id: Internal user ID

        Returns:
            Stripe customer ID if exists, otherwise None

        Raises:
            StripeServiceError: On database errors
        """
        try:
            if not BaseDatabaseService.subclasses:
                raise StripeServiceError("No database service implementation available")
            # fetch stripe customer id for user if it exists
            response = BaseDatabaseService.subclasses[0]().select_data(
                table_name="user_profiles", cols={"id": user_id}
            )
            if response and isinstance(response, List):
                customer = response[0]["stripe_customer_id"]
            elif response:
                customer = response

            else:
                customer = None
            return customer
        except Exception as e:
            logger.info(
                f"An unexpected error occured while retrieving stripe customer:{str(e)}"
            )
            raise StripeServiceError(
                "Unexpected error while retrieving stripe customer"
            )

    async def create_ephemeral_key(self, user_id: str, customer_id: str) -> str:
        """Create Stripe ephemeral key for client-side API access.

        Args:
            user_id: Internal user ID
            customer_id: Stripe customer ID

        Returns:
            Ephemeral key secret

        Raises:
            StripeServiceError: On key creation failure
        """
        try:
            ephemeral_key = stripe.EphemeralKey.create(
                customer=customer_id, stripe_version=stripe.api_version
            )
            return ephemeral_key.secret
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeServiceError(f"Error creating ephemeral key: {str(e)}")
        except Exception as e:
            logger.error(
                f"Failed to create ephemeral key: {user_id} with error: {str(e)}"
            )
            raise StripeServiceError("Unexpected error occured")

    async def create_setup_intent(self, user_id: str, customer_id: str) -> str:
        """Create Stripe setup intent for saving payment methods.

        Args:
            user_id: Internal user ID
            customer_id: Stripe customer ID

        Returns:
            Setup intent client secret

        Raises:
            StripeServiceError: On setup intent creation failure
        """
        try:
            setup_intent = stripe.SetupIntent.create(
                customer=customer_id,
                payment_method_types=["card"],
                usage="off_session",  # Indicates payment method can be charged when customer is not present
                metadata={"user_id": user_id},
            )
            return setup_intent.client_secret
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeServiceError(f"Error creating stripe customer: {str(e)}")
        except Exception as e:
            logger.error(
                f"Failed to create setup intent for user: {user_id} with error: {str(e)}"
            )
            raise StripeServiceError("Unexpected error while creating setup intent")

    async def create_subscription(
        self, customer_id: str, payment_method_id: str
    ) -> str:
        """Create subscription with trial period.

        Args:
            customer_id: Stripe customer ID
            payment_method_id: Stripe payment method ID

        Returns:
            Subscription ID

        Raises:
            StripeServiceError: On subscription creation failure
        """
        try:
            if not BaseDatabaseService.subclasses:
                raise StripeServiceError("No database service implementation available")
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": settings.STRIPE_PRICE_ID}],
                default_payment_method=payment_method_id,
                trial_period_days=3,  # 3 day trial period
            )
            # update user's subscription
            BaseDatabaseService.subclasses[0]().update_data(
                table_name="user_profiles",
                data={"stripe_subscription_id": subscription.id, "is_pro": True},
                cols={"stripe_customer_id": customer_id},
            )
            return subscription.id
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeServiceError(f"Error creating stripe customer: {str(e)}")
        except Exception as e:
            logger.error(
                f"Failed to create subscription for stripe customer: {customer_id} with error: {str(e)}"
            )
            raise StripeServiceError(
                "Unexpected error while creating user subscription"
            )

    async def create_customer_billing_portal(
        self, user_id: str, customer_id: str
    ) -> str:
        """Create Stripe billing portal session.

        Args:
            user_id: Internal user ID
            customer_id: Stripe customer ID

        Returns:
            URL to Stripe billing portal

        Raises:
            StripeServiceError: On portal session creation failure
        """
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f"https://macromealsapp.com/settings/billing",
            )
            return session.url
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeServiceError(
                f"Error creating stripe customer billing portal: {str(e)}"
            )
        except Exception as e:
            logger.error(
                f"Failed to create subscription for user: {user_id} with error: {str(e)}"
            )
            raise StripeServiceError(
                "Unexpected error while creating stripe customer billing portal"
            )

    async def get_customer_email(self, customer_id: str) -> Optional[str]:
        """Get customer email from Stripe.

        Args:
            customer_id: Stripe customer ID

        Returns:
            Customer email or None if not found
        """
        try:
            logger.info(f"Retrieving email for customer: {customer_id}")
            customer = stripe.Customer.retrieve(customer_id)
            return customer.get("email")
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error retrieving customer email: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving customer email: {str(e)}")
            return None


stripe_service = StripeService()
