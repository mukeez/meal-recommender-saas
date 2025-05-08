import logging
from fastapi import status
from fastapi.exceptions import HTTPException
import os
import stripe
from typing import Dict, Any, List
import time
from datetime import datetime

from app.models.billing import CheckoutSessionResponse, SubscriptionUpdate
from app.utils.helper_functions import remove_null_values
from app.services.base_database_service import BaseDatabaseService


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

    async def create_checkout_session(
        self, email: str, user_id: str
    ) -> CheckoutSessionResponse:
        try:
            logger.info(f"Creating checkout session for user: {user_id}")

            if not BaseDatabaseService.subclasses:
                raise StripeServiceError("No database service implementation available")

            # fetch stripe customer id for user if it exists
            response = await BaseDatabaseService.subclasses[0]().select_data(
                table_name="user_profiles", cols={"id": user_id}
            )
            if response and isinstance(response, List):
                customer = response[0]["stripe_customer_id"]
            elif response:
                customer = response

            else:
                customer = None

            params = {
                "payment_method_types": ["card"],
                "line_items": [{"price": self.price_id, "quantity": 1}],
                "mode": "subscription",
                "metadata": {"user_id": user_id},
                "success_url": f"https://macromealsapp.com/success?session_id={{CHECKOUT_SESSION_ID}}",
                "cancel_url": "https://macromealsapp.com/cancel",
            }
            if customer:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment details already exist for this user")
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
        """
        Handles the event when a new Stripe customer is created.

        Extracts the customer's email and Stripe customer ID from the session data
        and updates the corresponding user profile in the Supabase database with
        the Stripe customer ID.

        Args:
            session (Dict[str, Any]): A dictionary containing the Stripe session data,
                                       expected to have keys "customer_email" and "id".

        Raises:
            StripeServiceError: If the customer email is not found in the session
                                or if any error occurs during the database update.
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
            await BaseDatabaseService.subclasses[0]().update_data(
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
        """
         Update a user's subscription information based on the provided data.

        If `is_pro` is True, the user is marked as subscribed and their subscription
        start and end dates are updated. If False, the user is marked as unsubscribed.
        Also updates Stripe-related metadata such as the customer and subscription IDs.

        Args:
            customer (str): The stripe customer id of the user whose subscription is being updated.
            subscription_data (SubscriptionUpdate): Contains subscription details including
                pro status, Stripe customer ID, subscription ID, and the start/end dates.

        Returns:
            None
        """

        try:
            logger.info(
                f"Marking user with stripe customer id {customer} as subscribed"
            )

            if not BaseDatabaseService.subclasses:
                raise StripeServiceError("No database service implementation available")

            subscription_data_dict = remove_null_values(subscription_data.model_dump())

            # update user's stripe details
            await BaseDatabaseService.subclasses[0]().update_data(
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
        """
        Cancels the Stripe subscription for a given user.

        Fetches the user's Stripe subscription ID from the database and then
        initiates the cancellation through the Stripe API. The cancellation
        can be set to occur at the end of the current billing period or immediately.

        Args:
            user_id (str): The unique identifier of the user whose subscription
                           needs to be cancelled.
            cancel_at_period_end (bool, optional): A boolean indicating whether
                the cancellation should happen at the end of the current billing
                period (True) or immediately (False). Defaults to True.

        Returns:
            stripe.Subscription: The Stripe Subscription object representing the
                                 cancelled subscription.

        Raises:
            StripeServiceError: If no database service implementation is available,
                                if the Stripe subscription ID is not found for the user,
                                if there is an error interacting with the Stripe API,
                                or if any unexpected error occurs during the process.
        """
        try:
            logger.info(f"Cancelling subscription for user: {user_id}")
            if not BaseDatabaseService.subclasses:
                raise StripeServiceError("No database service implementation available")

            # fetch stripe subscription id for user if it exists
            response = await BaseDatabaseService.subclasses[0]().select_data(
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

            if cancel_at_period_end:
                sub = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                )
            else:
                sub = stripe.Subscription.delete(subscription_id)

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
        """
        Asynchronously retrieves the ID, start, and end dates of the first active subscription for a given Stripe customer, with retry logic.

        This function calls the Stripe API to retrieve the customer object and includes the expanded
        subscriptions data for efficient access. It iterates through the customer's subscriptions,
        prioritizing the first active subscription found. If an error occurs during the API call

        Args:
            customer_id (str): The ID of the Stripe customer.
            retries (int): The maximum number of retry attempts if the initial request fails or no active subscriptions are found. Defaults to 2.
            delay (float): The delay in seconds to wait between each retry attempt. Defaults to 2.0 seconds.

        Returns:
            Dict: A dictionary containing the 'subscription_id' (str), 'subscription_start' (datetime object),
                  and 'subscription_end' (datetime object) of the first active subscription found for the customer.
                  Returns an empty dictionary if no active subscriptions are found after all retries.

        Raises:
            StripeServiceError: If all retry attempts fail due to Stripe API errors or network issues.
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


stripe_service = StripeService()
