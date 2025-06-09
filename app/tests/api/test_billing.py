import pytest
from app.core.config import settings
from app.tests.constants.user import UserTestConstants
import json


@pytest.mark.asyncio
class TestBillingEndpoint:

    async def test_get_stripe_config_success(self, authenticated_client):
        """
        Test case to verify that the /stripe/config endpoint successfully returns
        the Stripe publishable key for an authenticated client.
        """
        response = authenticated_client.get(
            f"{settings.API_V1_STR}/billing/stripe-config",
        )

        assert response.status_code == 200

        assert response.json() == {"publishable_key": settings.STRIPE_PUBLISHABLE_KEY}

    async def test_create_setup_intent_success(
        self,
        authenticated_client,
        mock_stripe_create_customer,
        mock_stripe_create_ephemeral_key,
        mock_stripe_create_setup_intent,
    ):
        """
        Test case to verify that the /create-setup-intent endpoint successfully
        creates a Stripe Customer, Ephemeral Key, and Setup Intent,
        returning the necessary secrets and IDs for an authenticated client.
        """

        mock_stripe_create_customer.return_value = (
            UserTestConstants.MOCK_CUSTOMER_ID.value
        )
        mock_stripe_create_ephemeral_key.return_value = "ek_test_secret"
        mock_stripe_create_setup_intent.return_value = "si_test_secret_xyz"

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/billing/create-setup-intent",
            json={
                "user_id": UserTestConstants.MOCK_USER_ID.value,
                "email": UserTestConstants.MOCK_USER_EMAIL.value,
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "client_secret": "si_test_secret_xyz",
            "ephemeral_key": "ek_test_secret",
            "customer_id": UserTestConstants.MOCK_CUSTOMER_ID.value,
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        }

        # # assert stripe_service.create_stripe_customer called
        mock_stripe_create_customer.assert_called_once_with(
            user_id=UserTestConstants.MOCK_USER_ID.value,
            email=UserTestConstants.MOCK_USER_EMAIL.value,
        )

        # # assert stripe_service.create_ephemeral_key called
        mock_stripe_create_ephemeral_key.assert_called_once_with(
            user_id=UserTestConstants.MOCK_USER_ID.value,
            customer_id=UserTestConstants.MOCK_CUSTOMER_ID.value,
        )

        # # assert stripe_service.create_setup_intent called
        mock_stripe_create_setup_intent.assert_called_once_with(
            user_id=UserTestConstants.MOCK_USER_ID.value,
            customer_id=UserTestConstants.MOCK_CUSTOMER_ID.value,
        )

    async def test_create_checkout_session_subscription_success(
        self, authenticated_client, mock_stripe_create_checkout_session
    ):
        """
        Test case to verify that the /create-checkout-session endpoint successfully
        creates a Stripe Checkout Session for a subscription, returning the session URL.
        """

        mock_stripe_create_checkout_session.return_value = {
            "checkout_url": "https://checkout.stripe.com/test_session_url",
            "session_id": "124242",
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/billing/checkout",
            json={
                "email": UserTestConstants.MOCK_USER_EMAIL.value,
                "user_id": UserTestConstants.MOCK_USER_ID.value,
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "checkout_url": "https://checkout.stripe.com/test_session_url",
            "session_id": "124242",
        }

        mock_stripe_create_checkout_session.assert_called_once()

    async def test_cancel_user_subscription_at_period_end(
        self, authenticated_client, mock_stripe_cancel_subscription
    ):
        """
        Test case to verify that the /cancel-subscription endpoint successfully
        sets a user's Stripe subscription to cancel at the end of the current billing period.
        """

        expected_value = {
            "status": "cancelled",
            "subscription_id": "su12434",
            "cancel_at_period_end": True,
        }

        mock_stripe_cancel_subscription.return_value = expected_value

        response = authenticated_client.delete(
            f"{settings.API_V1_STR}/billing/cancel",
            params={"cancel_at_period_end": True},
        )

        assert response.status_code == 200

        assert response.json() == expected_value

        mock_stripe_cancel_subscription.assert_called_once_with(
            user_id=UserTestConstants.MOCK_USER_ID.value, cancel_at_period_end=True
        )

    async def test_cancel_user_subscription_immediately(
        self, authenticated_client, mock_stripe_cancel_subscription
    ):
        """
        Test case to verify that the /cancel-subscription endpoint successfully
        immediately cancels a user's Stripe subscription with proration.
        """
        expected_value = {
            "status": "cancelled",
            "subscription_id": "su12434",
            "cancel_at_period_end": False,
        }

        mock_stripe_cancel_subscription.return_value = expected_value

        response = authenticated_client.delete(
            f"{settings.API_V1_STR}/billing/cancel",
            params={"cancel_at_period_end": False},
        )

        assert response.status_code == 200

        assert response.json() == expected_value

        mock_stripe_cancel_subscription.assert_called_once_with(
            user_id=UserTestConstants.MOCK_USER_ID.value, cancel_at_period_end=False
        )

    async def test_create_customer_portal_session_success(
        self,
        authenticated_client,
        mock_stripe_get_customer,
        mock_stripe_create_customer_billing_portal,
    ):
        """
        Test case to verify that the /create-customer-portal-session endpoint successfully
        creates a Stripe Customer Portal session URL for an authenticated client.
        """

        expected_value = {"url": "https://billing.stripe.com/test_session_url"}

        mock_stripe_create_customer_billing_portal.return_value = expected_value

        mock_stripe_get_customer.return_value = UserTestConstants.MOCK_CUSTOMER_ID.value

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/billing/create-customer-portal-session",
        )

        assert response.status_code == 200

        assert response.json() == expected_value

        mock_stripe_get_customer.assert_called_once_with(
            user_id=UserTestConstants.MOCK_USER_ID.value
        )

        # assert stripe_service.create_customer_billing portal called
        mock_stripe_create_customer_billing_portal.assert_called_once_with(
            user_id=UserTestConstants.MOCK_USER_ID.value,
            customer_id=UserTestConstants.MOCK_CUSTOMER_ID.value,
        )

    async def test_create_customer_portal_session_user_not_found(
        self,
        authenticated_client,
        mock_stripe_get_customer,
        mock_stripe_create_customer_billing_portal,
    ):
        """
        Test case to verify that the /create-customer-portal-session endpoint
        returns a 404 Not Found error when the authenticated user does not have
        an associated Stripe customer ID.
        """

        expected_value = {"detail": "Customer not found."}

        mock_stripe_create_customer_billing_portal.return_value = expected_value

        mock_stripe_get_customer.return_value = None

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/billing/create-customer-portal-session",
        )

        assert response.status_code == 400

        assert response.json() == expected_value

        mock_stripe_get_customer.assert_called_once_with(
            user_id=UserTestConstants.MOCK_USER_ID.value
        )

        # assert stripe_service.create_customer_billing portal called
        mock_stripe_create_customer_billing_portal.assert_not_called()

    async def test_webhook_setup_intent_succeeded(
        self,
        authenticated_client,
        generate_stripe_signature_for_test,
        mock_stripe_verify_webhook_signature,
        mock_stripe_create_subscription,
        mock_stripe_get_customer_email,  # Add this fixture
        mock_mail_send_email,  # Add this fixture
    ):
        """
        Test case to verify that the webhook handler correctly processes a
        'setup_intent.succeeded' event by creating a new Stripe subscription
        for the associated customer and sending a welcome email.
        """

        test_payload_dict = {
            "id": "evt_1PQRSampleSuccess00000000000",
            "object": "event",
            "api_version": "2020-08-27",
            "created": 1716195600,
            "type": "setup_intent.succeeded",
            "data": {
                "object": {
                    "id": "seti_1PQRSampleSuccessSetupIntent",
                    "object": "setup_intent",
                    "client_secret": "seti_1PQRSampleSuccessSetupIntent_secret_SAMPLECLIENTSECRET",
                    "created": 1716195590,
                    "customer": UserTestConstants.MOCK_CUSTOMER_ID.value,
                    "description": f"Subscription setup for user_{UserTestConstants.MOCK_USER_ID.value}",
                    "latest_attempt": "setatt_1PQRSampleSuccessAttempt",
                    "payment_method": "pm_SampleCardSuccessPaymentMethod",
                    "payment_method_options": {
                        "card": {"request_three_d_secure": "automatic"}
                    },
                    "payment_method_types": ["card"],
                    "status": "succeeded",
                    "usage": "off_session",
                    "metadata": {"user_id": UserTestConstants.MOCK_USER_ID.value},
                }
            },
        }

        # Generate test signature header
        test_signature = generate_stripe_signature_for_test
        test_payload_bytes = json.dumps(test_payload_dict).encode("utf-8")

        mock_stripe_verify_webhook_signature.return_value = test_payload_dict

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/billing/webhook",
            content=test_payload_bytes,
            headers={
                "Stripe-Signature": test_signature,
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "message": "Setup intent and subscription creation completed succesfully",
        }

        # assert stripe_service.verify_webhook_signature called
        mock_stripe_verify_webhook_signature.assert_called_once()

        # assert stripe_service.create_subscription called
        mock_stripe_create_subscription.assert_called_once()

        # assert get_customer_email was called with the correct customer_id
        mock_stripe_get_customer_email.assert_called_once_with(
            UserTestConstants.MOCK_CUSTOMER_ID.value
        )

        # assert send_email was called with the correct parameters
        mock_mail_send_email.assert_called_once_with(
            recipient=UserTestConstants.MOCK_USER_EMAIL.value,
            subject="Welcome to Macro Meals Pro!",
            template_name="subscription_created.html",
            context={
                "subscription_type": "Macro Meals Pro",
                "trial_days": 3,
            },
        )

    async def test_webhook_checkout_session_completed(
        self,
        authenticated_client,
        generate_stripe_signature_for_test,
        mock_stripe_verify_webhook_signature,
        mock_stripe_handle_checkout_completed,
        mock_mail_send_email,  # Add this fixture
    ):
        """
        Test case to verify that the webhook handler correctly processes a
        'checkout.session.completed' event, including sending a welcome email.
        """
        test_payload_dict = {
            "id": "evt_test_webhook_async",
            "object": "event",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_async_123",
                    "object": "checkout.session",
                    "mode": "subscription",
                    "customer": UserTestConstants.MOCK_CUSTOMER_ID.value,
                    "subscription": "sub_test_async_789",
                    "metadata": {"user_id": UserTestConstants.MOCK_USER_ID.value},
                    "customer_details": {
                        "email": UserTestConstants.MOCK_USER_EMAIL.value
                    },
                }
            },
            "api_version": "2024-06-20",
        }

        # Generate test signature header
        test_signature = generate_stripe_signature_for_test
        test_payload_bytes = json.dumps(test_payload_dict).encode("utf-8")

        mock_stripe_verify_webhook_signature.return_value = test_payload_dict

        mock_stripe_handle_checkout_completed.return_value = (
            UserTestConstants.MOCK_USER_ID.value
        )

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/billing/webhook",
            content=test_payload_bytes,
            headers={
                "Stripe-Signature": test_signature,
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "message": "Checkout completed successfully",
        }

        # assert stripe_service.verify_webhook_signature called
        mock_stripe_verify_webhook_signature.assert_called_once()

        # assert stripe_service.verify_handle_checkout_completed called
        mock_stripe_handle_checkout_completed.assert_called_once()

        # assert send_email was called with the correct parameters
        mock_mail_send_email.assert_called_once_with(
            recipient=UserTestConstants.MOCK_USER_EMAIL.value,
            subject="Welcome to Macro Meals Pro!",
            template_name="subscription_created.html",
            context={
                "subscription_type": "Macro Meals Pro",
                "trial_days": 3,
            },
        )

    async def test_webhook_invoice_paid(
        self,
        authenticated_client,
        generate_stripe_signature_for_test,
        mock_stripe_verify_webhook_signature,
        mock_stripe_update_user_subscription,
    ):
        """
        Test case to verify that the webhook handler correctly processes an
        'invoice.paid' event, typically by updating the user's subscription
        status and extending their access based on successful payment.
        """

        test_payload_dict = {
            "id": "evt_test_webhook_async",
            "object": "event",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_1RJOA8QuviqFcsStln1LLNew",
                    "object": "invoice",
                    "account_country": "GB",
                    "account_name": "EMIT sandbox",
                    "billing_reason": "subscription_create",
                    "collection_method": "charge_automatically",
                    "created": 1745971568,
                    "currency": "usd",
                    "customer": "cus_SDppqYZibGh4sY",
                    "lines": {
                        "object": "list",
                        "data": [
                            {
                                "id": "il_1RJOA8QuviqFcsStkAqVg84G",
                                "object": "line_item",
                                "amount": 0,
                                "currency": "usd",
                                "description": "MacroMeals Pro",
                                "invoice": "in_1RJOA8QuviqFcsStln1LLNew",
                                "period": {"end": 1746230766, "start": 1745971566},
                            }
                        ],
                    },
                }
            },
        }

        # Generate test signature header
        test_signature = generate_stripe_signature_for_test
        test_payload_bytes = json.dumps(test_payload_dict).encode("utf-8")

        mock_stripe_verify_webhook_signature.return_value = test_payload_dict

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/billing/webhook",
            content=test_payload_bytes,
            headers={
                "Stripe-Signature": test_signature,
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "message": "Subscription renewed",
        }

        # assert stripe_service.verify_webhook_signature called
        mock_stripe_verify_webhook_signature.assert_called_once()

        # assert stripe_service.update_stripe_user_subscription called
        mock_stripe_update_user_subscription.assert_called_once()

    async def test_webhook_subscription_deleted(
        self,
        authenticated_client,
        generate_stripe_signature_for_test,
        mock_stripe_verify_webhook_signature,
        mock_stripe_update_user_subscription,
        mock_stripe_get_customer_email,  # Add this fixture
        mock_mail_send_email,  # Add this fixture
    ):
        """
        Test case to verify that the webhook handler correctly processes a
        'customer.subscription.deleted' event by marking the user's subscription
        as inactive and sending a cancellation email.
        """
        from app.models.billing import SubscriptionUpdate

        test_payload_dict = {
            "id": "evt_1PQRDeletedEventMinimal",
            "object": "event",
            "api_version": "2024-06-20",
            "created": 1716196000,
            "livemode": False,
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_MinimalDeletedSubscriptionID",
                    "object": "subscription",
                    "cancel_at_period_end": False,
                    "canceled_at": 1716196000,
                    "current_period_end": 1716196000,
                    "customer": UserTestConstants.MOCK_CUSTOMER_ID.value,
                    "ended_at": 1716196000,
                    "status": "canceled",
                    "metadata": {"user_id": UserTestConstants.MOCK_USER_ID.value},
                }
            },
        }

        # Generate test signature header
        test_signature = generate_stripe_signature_for_test
        test_payload_bytes = json.dumps(test_payload_dict).encode("utf-8")

        mock_stripe_verify_webhook_signature.return_value = test_payload_dict

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/billing/webhook",
            content=test_payload_bytes,
            headers={
                "Stripe-Signature": test_signature,
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "success",
            "message": "Subscription cancelled successfully",
        }

        # assert stripe_service.verify_webhook_signature called
        mock_stripe_verify_webhook_signature.assert_called_once()

        # assert stripe_service.update_stripe_user_subscription called
        mock_stripe_update_user_subscription.assert_called_once()

        # assert get_customer_email was called with the correct customer_id
        mock_stripe_get_customer_email.assert_called_once_with(
            UserTestConstants.MOCK_CUSTOMER_ID.value
        )

        # assert send_email was called with the correct parameters for cancellation
        mock_mail_send_email.assert_called_once()
        # Use a deeper assertion to check context
        args, kwargs = mock_mail_send_email.call_args
        assert kwargs["recipient"] == UserTestConstants.MOCK_USER_EMAIL.value
        assert kwargs["subject"] == "Your Macro Meals Pro Subscription"
        assert kwargs["template_name"] == "subscription_cancelled.html"
        assert "subscription_type" in kwargs["context"]
        assert kwargs["context"]["subscription_type"] == "Macro Meals Pro"
        assert "cancellation_date" in kwargs["context"]
