import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock
from app.tests.constants.user import UserTestConstants


@pytest.fixture(scope="function")
def mock_stripe_create_customer(mocker):
    """Fixture to patch and provide a mock for stripe_service.create_stripe_customer."""
    mock = mocker.patch(
        "app.api.endpoints.billing.stripe_service.create_stripe_customer",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_stripe_get_customer(mocker):
    """Fixture to patch and provide a mock for stripe_service.get_stripe_customer."""
    mock = mocker.patch(
        "app.api.endpoints.billing.stripe_service.get_stripe_customer",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_stripe_create_ephemeral_key(mocker):
    """Fixture to patch and provide a mock for stripe_service.create_ephemeral_key."""
    mock = mocker.patch(
        "app.api.endpoints.billing.stripe_service.create_ephemeral_key",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_stripe_create_setup_intent(mocker):
    """Fixture to patch and provide a mock for stripe_service.create_setup_intent."""
    mock = mocker.patch(
        "app.api.endpoints.billing.stripe_service.create_setup_intent",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_stripe_create_subscription(mocker):
    """Fixture to patch and provide a mock for stripe_service.create_subscription."""
    mock = mocker.patch(
        "app.api.endpoints.billing.stripe_service.create_subscription",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_stripe_create_checkout_session(mocker):
    """Fixture to patch and provide a mock for stripe_service.create_checkout_session."""
    mock = mocker.patch(
        "app.api.endpoints.billing.stripe_service.create_checkout_session",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_stripe_cancel_subscription(mocker):
    """Fixture to patch and provide a mock for stripe_service.cancel_user_subscription."""
    mock = mocker.patch(
        "app.api.endpoints.billing.stripe_service.cancel_user_subscription",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_stripe_create_customer_billing_portal(mocker):
    """Fixture to patch and provide a mock for stripe_service.create_customer_billing_portal."""
    mock = mocker.patch(
        "app.api.endpoints.billing.stripe_service.create_customer_billing_portal",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_stripe_update_user_subscription(mocker):
    """Fixture to patch and provide a mock for stripe_service.update_stripe_user_subscription."""
    mock = mocker.patch(
        "app.api.endpoints.billing.stripe_service.update_stripe_user_subscription",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_stripe_verify_webhook_signature(mocker):
    """Fixture to patch and provide a mock for stripe_service.verify_webhook_signature."""
    mock = mocker.patch(
        "app.api.endpoints.billing.stripe_service.verify_webhook_signature"
    )
    return mock


@pytest.fixture(scope="function")
def mock_stripe_handle_checkout_completed(mocker):
    """Fixture to patch and provide a mock for stripe_service.handle_checkout_completed."""
    mock = mocker.patch(
        "app.api.endpoints.billing.stripe_service.handle_checkout_completed",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def generate_stripe_signature_for_test():
    """Fixture to generate stripe signature"""
    return "t=123456789,v1=fake_signature"


@pytest.fixture
def mock_stripe_get_customer_email(monkeypatch):
    """
    Mock the stripe_service.get_customer_email method to return a test email.
    """
    mock = AsyncMock(return_value=UserTestConstants.MOCK_USER_EMAIL.value)
    monkeypatch.setattr(
        "app.services.stripe_service.stripe_service.get_customer_email", mock
    )
    return mock


@pytest.fixture
def mock_mail_send_email(monkeypatch):
    """
    Mock the mail_service.send_email method.
    """
    mock = AsyncMock(return_value={
        "status": True,
        "message": "Email Successfully Sent.",
        "message_id": "mock-email-id-123",
        "response": {"MessageId": "mock-email-id-123"}
    })
    monkeypatch.setattr(
        "app.services.mail_service.mail_service.send_email", mock
    )
    return mock
