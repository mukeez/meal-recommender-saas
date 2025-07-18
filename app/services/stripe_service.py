"""Stripe Service Module
Handles Stripe API interactions for billing, subscriptions and customer management.
"""

import logging
from fastapi import status
from fastapi.exceptions import HTTPException
import os
import stripe
from typing import Dict, Any, List, Literal, Optional
import time
from datetime import datetime, timezone
import httpx

from app.models.billing import CheckoutSessionResponse
from app.utils.helper_functions import remove_null_values
from app.services.base_database_service import BaseDatabaseService
from app.services.user_service import user_service
from app.core.config import settings


logger = logging.getLogger(__name__)


class StripeServiceError(Exception):
    """Custom exception for Stripe service operations."""

    pass


class StripeService:
    """Service for managing Stripe billing and subscriptions."""

    def __init__(self):
        """Initialize with Stripe API credentials and configuration."""
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        self.monthly_price_id = settings.STRIPE_MONTHLY_PRICE_ID
        self.yearly_price_id = settings.STRIPE_YEARLY_PRICE_ID

        if not stripe.api_key:
            logger.error("STRIPE_SECRET_KEY environment variable is not set")
            raise ValueError("STRIPE_SECRET_KEY environment variable is not set")

        if not self.webhook_secret:
            logger.warning("STRIPE_WEBHOOK_SECRET environment variable is not set")

        if not self.monthly_price_id or not self.yearly_price_id:
            logger.error(
                "STRIPE_MONTHLY_PRICE_ID or STRIPE_YEARLY_PRICE_ID environment variable is not set"
            )
            raise ValueError(
                "STRIPE_MONTHLY_PRICE_ID or STRIPE_YEARLY_PRICE_ID environment variable is not set"
            )

    async def create_checkout_session(
        self, email: str, user_id: str, plan: Literal["monthly", "yearly"] = "monthly"
    ) -> CheckoutSessionResponse:
        """Create a Stripe checkout session for subscription.

        Args:
            email: User's email address
            user_id: User's unique identifier
            plan: Subscription plan (monthly or yearly)

        Returns:
            CheckoutSessionResponse with checkout URL and session ID

        Raises:
            StripeServiceError: On checkout session creation failure
            HTTPException: If user already has payment details or active subscription
        """
        try:
            logger.info(f"Creating checkout session for user: {user_id}")

            # Check for active subscription
            has_active_sub = await self.has_active_subscription(user_id)
            if has_active_sub:
                logger.warning(
                    f"User {user_id} attempted to create checkout session with existing active subscription"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="You already have an active subscription. Please manage your existing subscription in your account settings.",
                )

            # get stripe customer id if exists (for trial check)
            customer = await self.get_stripe_customer(user_id=user_id)

            # Create customer if it doesn't exist
            if not customer:
                logger.info(f"Creating new Stripe customer for user: {user_id}")
                customer = await self.create_stripe_customer(
                    user_id=user_id, email=email
                )
                logger.info(f"Created Stripe customer: {customer}")

            # Check if user has already used their trial
            user_profile = await user_service.get_user_profile(user_id)
            has_used_trial = user_profile.has_used_trial

            params = {
                "payment_method_types": ["card"],
                "mode": "subscription",
                "metadata": {
                    "user_id": user_id,
                    "has_trial": str(not has_used_trial),
                    "plan": plan,
                },
                "success_url": f"https://macromealsapp.com/success?session_id={{CHECKOUT_SESSION_ID}}",
                "cancel_url": "https://macromealsapp.com/cancel",
                "customer": customer,
            }
            if plan == "yearly":
                params["line_items"] = [{"price": self.yearly_price_id, "quantity": 1}]
            else:
                params["line_items"] = [{"price": self.monthly_price_id, "quantity": 1}]

            # Add metadata to subscription
            subscription_data: dict = {
                "metadata": {
                    "user_id": user_id,
                    "has_trial": str(not has_used_trial),
                    "plan": plan,
                }
            }

            # Add trial period if user hasn't used it before
            if not has_used_trial:
                subscription_data["trial_period_days"] = 7
                logger.info(f"User {user_id} eligible for 7-day trial")
            else:
                logger.info(f"User {user_id} has already used trial - no trial period")

            params["subscription_data"] = subscription_data

            checkout_session = stripe.checkout.Session.create(**params)

            logger.info(f"Checkout session created: {checkout_session.id}")

            if not checkout_session.url:
                raise StripeServiceError("Checkout session URL is missing")

            return CheckoutSessionResponse(
                checkout_url=checkout_session.url, session_id=checkout_session.id
            )

        except stripe.StripeError as e:
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
        except stripe.SignatureVerificationError as e:
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
                customer, subscription_data={"is_pro": True}
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
        self, customer: str, subscription_data: Dict[str, Any]
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

            # update user's stripe details
            BaseDatabaseService.subclasses[0]().update_data(
                table_name="user_profiles",
                data=subscription_data,
                cols={"stripe_customer_id": customer},
            )

        except Exception as e:
            logger.error(f"Error updating user subscription: {str(e)}")
            raise StripeServiceError(f"Error updating user subscription: {str(e)}")

    async def cancel_user_subscription(
        self, subscription_id: str, cancel_at_period_end: bool = True
    ) -> stripe.Subscription:
        """Cancel a Stripe subscription by its ID.

        Args:
            subscription_id: The ID of the Stripe subscription to cancel.
            cancel_at_period_end: Whether to cancel at billing period end.

        Returns:
            Updated Stripe Subscription object.

        Raises:
            StripeServiceError: When subscription not found or cancellation fails.
        """
        try:
            logger.info(f"Cancelling subscription: {subscription_id}")

            if cancel_at_period_end:
                sub = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                )
            else:
                sub = stripe.Subscription.delete(subscription_id)

            return sub
        except stripe.StripeError as e:
            logger.error(f"Stripe error cancelling subscription {subscription_id}: {str(e)}")
            raise StripeServiceError(f"Error cancelling subscription: {str(e)}")
        except Exception as e:
            logger.error(
                f"Failed to cancel subscription {subscription_id} with error: {str(e)}"
            )
            raise StripeServiceError("Unexpected error while cancelling subscription")

    async def reactivate_user_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Reactivate a subscription that was set to cancel at period end.

        Args:
            subscription_id: The ID of the subscription to reactivate.

        Returns:
            Updated Stripe Subscription object.

        Raises:
            StripeServiceError: When subscription not found, not eligible for reactivation, or reactivation fails.
        """
        try:
            logger.info(f"Reactivating subscription: {subscription_id}")

            # Get subscription details from Stripe
            subscription = stripe.Subscription.retrieve(subscription_id)

            # Check if subscription is eligible for reactivation
            if not subscription.cancel_at_period_end:
                raise StripeServiceError(
                    "Subscription is not set to cancel - no reactivation needed"
                )

            # Check if subscription is still active (hasn't ended yet)
            if subscription.status not in ["active", "trialing"]:
                raise StripeServiceError(
                    f"Subscription cannot be reactivated - current status: {subscription.status}"
                )

            # Check if we're still within the current period
            if datetime.now(timezone.utc) >= datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            ):
                raise StripeServiceError(
                    "Subscription period has already ended - cannot reactivate"
                )

            # Reactivate the subscription
            reactivated_subscription = stripe.Subscription.modify(
                subscription_id, cancel_at_period_end=False
            )

            logger.info(
                f"Successfully reactivated subscription {subscription_id}"
            )
            return reactivated_subscription

        except stripe.StripeError as e:
            logger.error(f"Stripe error reactivating subscription {subscription_id}: {str(e)}")
            raise StripeServiceError(f"Error reactivating subscription: {str(e)}")
        except StripeServiceError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to reactivate subscription {subscription_id} with error: {str(e)}"
            )
            raise StripeServiceError("Unexpected error while reactivating subscription")

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
                subscriptions = (
                    customer.subscriptions.data if customer.subscriptions else []
                )
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
            except (stripe.StripeError, StripeServiceError) as e:
                if attempt == retries:
                    raise StripeServiceError(
                        f"Failed to retrieve subscription after {retries} attempts: {e}"
                    )
                time.sleep(delay)

        # This should never be reached due to the exception handling above
        raise StripeServiceError(
            f"Failed to retrieve subscription for customer {customer_id}"
        )

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
        except stripe.StripeError as e:
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
            return ephemeral_key["secret"]
        except stripe.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeServiceError(f"Error creating ephemeral key: {str(e)}")
        except Exception as e:
            logger.error(
                f"Failed to create ephemeral key: {user_id} with error: {str(e)}"
            )
            raise StripeServiceError("Unexpected error occured")

    async def create_setup_intent(
        self,
        user_id: str,
        customer_id: str,
        plan: Literal["monthly", "yearly"] = "monthly",
    ) -> str:
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
                metadata={"user_id": user_id, "plan": plan},
            )
            if not setup_intent.client_secret:
                raise StripeServiceError("Setup intent client secret is missing")
            return setup_intent.client_secret
        except stripe.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeServiceError(f"Error creating stripe customer: {str(e)}")
        except Exception as e:
            logger.error(
                f"Failed to create setup intent for user: {user_id} with error: {str(e)}"
            )
            raise StripeServiceError("Unexpected error while creating setup intent")

    async def create_subscription(
        self,
        customer_id: str,
        payment_method_id: str,
        user_id: str,
        plan: Literal["monthly", "yearly"] = "monthly",
    ) -> str:
        """Create subscription with conditional trial period.

        Args:
            customer_id: Stripe customer ID
            payment_method_id: Stripe payment method ID
            user_id: Internal user ID
            plan: Subscription plan (monthly or yearly)

        Returns:
            Subscription ID

        Raises:
            StripeServiceError: On subscription creation failure
        """
        try:
            if not BaseDatabaseService.subclasses:
                raise StripeServiceError("No database service implementation available")

            # CRITICAL: Check for existing active subscriptions in Stripe first
            existing_subscriptions = await self.get_active_stripe_subscriptions(
                customer_id
            )
            if existing_subscriptions:
                logger.warning(
                    f"Customer {customer_id} already has {len(existing_subscriptions)} active subscription(s)"
                )
                # Use the first active subscription instead of creating a new one
                existing_sub = existing_subscriptions[0]

                # Update database with existing subscription
                BaseDatabaseService.subclasses[0]().update_data(
                    table_name="user_profiles",
                    data={"stripe_subscription_id": existing_sub.id, "is_pro": True},
                    cols={"stripe_customer_id": customer_id},
                )

                logger.info(
                    f"Using existing subscription {existing_sub.id} for customer {customer_id}"
                )
                return existing_sub.id

            # Check if user has already used their trial
            from app.services.user_service import user_service

            user_profile = await user_service.get_user_profile(user_id)
            has_used_trial = user_profile.has_used_trial

            if plan == "yearly":
                price_id = settings.STRIPE_YEARLY_PRICE_ID
            else:
                price_id = settings.STRIPE_MONTHLY_PRICE_ID

            if not price_id:
                raise StripeServiceError("Price ID not configured")

            # Build subscription parameters
            subscription_params = {
                "customer": customer_id,
                "items": [{"price": price_id}],
                "default_payment_method": payment_method_id,
                "metadata": {"user_id": user_id, "has_trial": str(not has_used_trial)},
            }

            # Add trial period only if user hasn't used it before
            if not has_used_trial:
                subscription_params["trial_period_days"] = 7
                logger.info(
                    f"Creating subscription with 7-day trial for user: {user_id}"
                )
            else:
                logger.info(f"Creating subscription without trial for user: {user_id}")

            # Create the subscription
            subscription = stripe.Subscription.create(**subscription_params)

            # Double-check no duplicate was created during the API call
            all_subscriptions = await self.get_active_stripe_subscriptions(customer_id)
            if len(all_subscriptions) > 1:
                logger.warning(
                    f"Multiple subscriptions detected for customer {customer_id}. Using the newest one."
                )
                # Cancel all but the newest subscription
                newest_sub = max(all_subscriptions, key=lambda s: s.created)
                for sub in all_subscriptions:
                    if sub.id != newest_sub.id:
                        logger.info(f"Cancelling duplicate subscription {sub.id}")
                        try:
                            stripe.Subscription.cancel(sub.id)
                        except Exception as e:
                            logger.error(
                                f"Failed to cancel duplicate subscription {sub.id}: {str(e)}"
                            )
                subscription = newest_sub

            # update user's subscription
            BaseDatabaseService.subclasses[0]().update_data(
                table_name="user_profiles",
                data={"stripe_subscription_id": subscription.id, "is_pro": True},
                cols={"stripe_customer_id": customer_id},
            )

            logger.info(
                f"Successfully created subscription {subscription.id} for customer {customer_id}"
            )
            return subscription.id

        except stripe.StripeError as e:
            logger.error(f"Stripe error: {str(e)}")
            raise StripeServiceError(f"Error creating stripe subscription: {str(e)}")
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
        except stripe.StripeError as e:
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
        except stripe.StripeError as e:
            logger.error(f"Stripe error retrieving customer email: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving customer email: {str(e)}")
            return None

    async def has_active_subscription(self, user_id: str) -> bool:
        """Check if user has an active subscription.

        Args:
            user_id: Internal user ID

        Returns:
            True if user has active subscription, False otherwise

        Raises:
            StripeServiceError: On database errors
        """
        try:
            logger.info(f"Checking subscription status for user: {user_id}")

            if not BaseDatabaseService.subclasses:
                raise StripeServiceError("No database service implementation available")

            # Get user profile to check subscription status
            response = BaseDatabaseService.subclasses[0]().select_data(
                table_name="user_profiles", cols={"id": user_id}
            )

            if not response:
                logger.info(f"No profile found for user: {user_id}")
                return False

            # Handle both list and dict responses
            user_data = response[0] if isinstance(response, List) else response

            # Check if user is marked as pro and has subscription ID
            is_pro = user_data.get("is_pro", False)
            subscription_id = user_data.get("stripe_subscription_id")
            customer_id = user_data.get("stripe_customer_id")

            logger.info(
                f"User {user_id} - is_pro: {is_pro}, subscription_id: {subscription_id}, customer_id: {customer_id}"
            )

            # If database shows user as pro with subscription, verify with Stripe
            if is_pro and subscription_id and customer_id:
                try:
                    # Double-check with Stripe to ensure subscription is actually active
                    active_subscriptions = await self.get_active_stripe_subscriptions(
                        customer_id
                    )

                    # Check if the stored subscription ID is among active ones
                    active_sub_ids = [sub.id for sub in active_subscriptions]
                    if subscription_id in active_sub_ids:
                        logger.info(
                            f"Subscription {subscription_id} confirmed active in Stripe"
                        )
                        return True
                    else:
                        logger.warning(
                            f"Database shows subscription {subscription_id} but it's not active in Stripe"
                        )
                        # Update database to reflect actual state
                        BaseDatabaseService.subclasses[0]().update_data(
                            table_name="user_profiles",
                            data={"is_pro": False, "stripe_subscription_id": None},
                            cols={"id": user_id},
                        )
                        return False

                except StripeServiceError as e:
                    logger.warning(
                        f"Could not verify subscription with Stripe: {str(e)}"
                    )
                    # Fall back to database status if Stripe is unavailable
                    return bool(is_pro and subscription_id)

            # If customer exists but no subscription in database, check Stripe
            elif customer_id:
                try:
                    active_subscriptions = await self.get_active_stripe_subscriptions(
                        customer_id
                    )
                    if active_subscriptions:
                        logger.info(
                            f"Found {len(active_subscriptions)} active subscription(s) in Stripe not reflected in database"
                        )
                        # Update database with the first active subscription
                        latest_sub = max(active_subscriptions, key=lambda s: s.created)
                        BaseDatabaseService.subclasses[0]().update_data(
                            table_name="user_profiles",
                            data={
                                "is_pro": True,
                                "stripe_subscription_id": latest_sub.id,
                            },
                            cols={"id": user_id},
                        )
                        return True

                except StripeServiceError as e:
                    logger.warning(f"Could not check Stripe subscriptions: {str(e)}")

            return False

        except Exception as e:
            logger.error(
                f"Error checking subscription status for user {user_id}: {str(e)}"
            )
            raise StripeServiceError(f"Error checking subscription status: {str(e)}")

    async def get_active_stripe_subscriptions(
        self, customer_id: str
    ) -> List[stripe.Subscription]:
        """Get all active subscriptions for a customer from Stripe.

        Args:
            customer_id: Stripe customer ID

        Returns:
            List of active Stripe subscriptions

        Raises:
            StripeServiceError: On Stripe API errors
        """
        try:
            logger.info(
                f"Checking for active subscriptions for customer: {customer_id}"
            )

            # Retrieve customer with expanded subscriptions
            customer = stripe.Customer.retrieve(customer_id, expand=["subscriptions"])

            # Filter for active subscriptions (active, trialing, past_due)
            active_statuses = ["active", "trialing", "past_due"]
            active_subscriptions = [
                sub
                for sub in (
                    customer.subscriptions.data if customer.subscriptions else []
                )
                if sub.status in active_statuses
            ]

            logger.info(
                f"Found {len(active_subscriptions)} active subscription(s) for customer {customer_id}"
            )
            return active_subscriptions

        except stripe.StripeError as e:
            logger.error(f"Stripe error retrieving subscriptions: {str(e)}")
            raise StripeServiceError(
                f"Error retrieving customer subscriptions: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error retrieving subscriptions: {str(e)}")
            raise StripeServiceError(
                f"Unexpected error retrieving subscriptions: {str(e)}"
            )

    async def get_subscription_details(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive subscription details including plan information.

        Args:
            user_id: Internal user ID

        Returns:
            Dictionary with detailed subscription information

        Raises:
            StripeServiceError: On Stripe API errors
        """
        try:
            logger.info(
                f"Getting detailed subscription information for user: {user_id}"
            )

            # Get customer ID
            customer_id = await self.get_stripe_customer(user_id)
            if not customer_id:
                return {"has_subscription": False}

            # Get active subscriptions
            active_subscriptions = await self.get_active_stripe_subscriptions(
                customer_id
            )

            if not active_subscriptions:
                return {"has_subscription": False}

            # Get the most recent subscription
            subscription = max(active_subscriptions, key=lambda s: s.created)

            # Get the subscription with expanded price data
            detailed_subscription = stripe.Subscription.retrieve(
                subscription.id, expand=["items.data.price.product"]
            )

            # Extract price information
            subscription_item = (
                detailed_subscription["items"]["data"][0]
                if detailed_subscription.get("items") and detailed_subscription["items"].get("data")
                else None
            )
            price = subscription_item["price"] if subscription_item else None

            # Determine plan type based on price ID
            plan_type = None
            plan_name = None
            if price:
                if price["id"] == self.monthly_price_id:
                    plan_type = "monthly"
                    plan_name = "Monthly Plan"
                elif price["id"] == self.yearly_price_id:
                    plan_type = "yearly"
                    plan_name = "Yearly Plan"

            # Calculate next billing date
            next_billing_date = None
            if detailed_subscription.get("status") in ["active", "trialing"]:
                trial_end = detailed_subscription.get("trial_end")
                if (
                    trial_end is not None
                    and detailed_subscription.get("status") == "trialing"
                ):
                    # If in trial, next billing is trial end
                    next_billing_date = datetime.fromtimestamp(trial_end)
                elif not detailed_subscription.get("cancel_at_period_end"):
                    # If not cancelling, next billing is current period end
                    current_period_end = detailed_subscription.get("current_period_end")
                    if current_period_end is not None:
                        next_billing_date = datetime.fromtimestamp(current_period_end)

            cps = datetime.fromtimestamp(detailed_subscription["items"]["data"][0]["current_period_start"]).date()
            cpe = datetime.fromtimestamp(detailed_subscription["items"]["data"][0]["current_period_end"]).date()
            trial_end_val = detailed_subscription.get("trial_end")
            created = detailed_subscription.get("created")

            return {
                "has_subscription": True,
                "subscription_id": detailed_subscription.get("id"),
                "status": detailed_subscription.get("status"),
                "plan": plan_type,
                "plan_name": plan_name,
                "amount": (
                    price["unit_amount"] / 100 if price and price.get("unit_amount") else None
                ),
                "currency": (
                    price["currency"].upper() if price and price.get("currency") else None
                ),
                "billing_interval": (
                    price["recurring"]["interval"]
                    if price
                    and price.get("recurring")
                    and price["recurring"].get("interval")
                    else None
                ),
                "current_period_start": cps,
                "current_period_end": cpe,
                "next_billing_date": next_billing_date,
                "trial_end": (
                    datetime.fromtimestamp(trial_end_val) if trial_end_val is not None else None
                ),
                "cancel_at_period_end": detailed_subscription.get(
                    "cancel_at_period_end"
                ),
                "created": datetime.fromtimestamp(created) if created is not None else None,
            }

        except stripe.StripeError as e:
            logger.error(f"Stripe error getting subscription details: {str(e)}")
            raise StripeServiceError(f"Error retrieving subscription details: {str(e)}")
        except Exception as e:
            logger.error(
                f"Error getting subscription details for user {user_id}: {str(e)}"
            )
            raise StripeServiceError(f"Error getting subscription details: {str(e)}")

    async def is_webhook_event_processed(self, event_id: str) -> bool:
        """Check if a webhook event has already been processed.

        Args:
            event_id: Stripe event ID

        Returns:
            True if the event has been processed, False otherwise
        """
        import httpx
        from app.core.config import settings

        logger.info(f"Checking if webhook event {event_id} has been processed")

        try:
            if not settings.SUPABASE_SERVICE_ROLE_KEY:
                logger.error("SUPABASE_SERVICE_ROLE_KEY is not configured")
                return False

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.SUPABASE_URL}/rest/v1/webhook_events",
                    headers={
                        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                        "Content-Type": "application/json",
                    },
                    params={"event_id": f"eq.{event_id}"},
                )

                if response.status_code == 200:
                    events = response.json()
                    is_processed = len(events) > 0
                    logger.info(f"Event {event_id} processed status: {is_processed}")
                    return is_processed
                else:
                    logger.warning(
                        f"Failed to check webhook event status: {response.status_code}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error checking webhook event: {str(e)}")
            return False

    async def mark_webhook_event_processed(self, event_id: str) -> None:
        """Mark a webhook event as processed to prevent duplicate processing.

        Args:
            event_id: Stripe event ID
        """

        logger.info(f"Marking webhook event {event_id} as processed")

        try:
            if not settings.SUPABASE_SERVICE_ROLE_KEY:
                logger.error("SUPABASE_SERVICE_ROLE_KEY is not configured")
                return

            webhook_event = {
                "event_id": event_id,
                "processed_at": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.SUPABASE_URL}/rest/v1/webhook_events",
                    headers={
                        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                        "Content-Type": "application/json",
                        "Prefer": "return=representation",
                    },
                    json=webhook_event,
                )

                if response.status_code not in (201, 200):
                    error_detail = "Failed to mark webhook event as processed"
                    try:
                        error_data = response.json()
                        if "message" in error_data:
                            error_detail = error_data["message"]
                    except Exception:
                        pass

                    logger.error(
                        f"Failed to mark event {event_id} as processed: {error_detail}"
                    )

                else:
                    logger.info(f"Successfully marked event {event_id} as processed")

        except Exception as e:
            logger.error(f"Error marking webhook event as processed: {str(e)}")


stripe_service = StripeService()
