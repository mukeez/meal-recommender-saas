import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timedelta
import hashlib


@pytest.fixture(scope="function")
def mock_auth_httpx_client_post(mocker):
    """Fixture to patch and provide a mock for httpx client."""
    mock = mocker.patch("app.api.endpoints.auth.httpx.AsyncClient.post")
    return mock


@pytest.fixture(scope="function")
def mock_auth_httpx_client_put(mocker):
    """Fixture to patch and provide a mock for httpx client."""
    mock = mocker.patch("app.api.endpoints.auth.httpx.AsyncClient.put")
    return mock


@pytest.fixture(scope="function")
def mock_user_service(mocker):
    """Fixture to patch and provide a mock for user_service."""
    mock = mocker.patch(
        "app.api.endpoints.auth.user_service",
        autospec=True
    )
    mock.get_user_by_email = AsyncMock()
    mock.store_otp = AsyncMock()
    mock.get_otp = AsyncMock()
    mock.store_session_token = AsyncMock()
    mock.get_session_token = AsyncMock()
    mock.update_password = AsyncMock()
    mock.invalidate_otp = AsyncMock()
    mock.invalidate_session_token = AsyncMock()
    return mock


@pytest.fixture(scope="function")
def mock_mail_service(mocker):
    """Fixture to patch and provide a mock for mail_service."""
    mock = mocker.patch(
        "app.api.endpoints.auth.mail_service",
        autospec=True
    )
    mock.send_email = AsyncMock()
    return mock


@pytest.fixture(scope="function")
def mock_user_get_by_email(mocker):
    """Fixture to patch and provide a mock for user_service.get_user_by_email."""
    mock = mocker.patch(
        "app.api.endpoints.auth.user_service.get_user_by_email",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_user_store_otp(mocker):
    """Fixture to patch and provide a mock for user_service.store_otp."""
    mock = mocker.patch(
        "app.api.endpoints.auth.user_service.store_otp",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_mail_send_email(mocker):
    """Fixture to patch and provide a mock for mail_service.send_email."""
    mock = mocker.patch(
        "app.api.endpoints.auth.mail_service.send_email",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_user_get_otp(mocker):
    """Fixture to patch and provide a mock for user_service.get_otp."""
    mock = mocker.patch(
        "app.api.endpoints.auth.user_service.get_otp",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_user_store_session_token(mocker):
    """Fixture to patch and provide a mock for user_service.store_session_token."""
    mock = mocker.patch(
        "app.api.endpoints.auth.user_service.store_session_token",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_user_get_session_token(mocker):
    """Fixture to patch and provide a mock for user_service.get_session_token."""
    mock = mocker.patch(
        "app.api.endpoints.auth.user_service.get_session_token",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_user_update_password(mocker):
    """Fixture to patch and provide a mock for user_service.update_password."""
    mock = mocker.patch(
        "app.api.endpoints.auth.user_service.update_password",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_user_invalidate_otp(mocker):
    """Fixture to patch and provide a mock for user_service.invalidate_otp."""
    mock = mocker.patch(
        "app.api.endpoints.auth.user_service.invalidate_otp",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_user_invalidate_session_token(mocker):
    """Fixture to patch and provide a mock for user_service.invalidate_session_token."""
    mock = mocker.patch(
        "app.api.endpoints.auth.user_service.invalidate_session_token",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_valid_otp_entry():
    """Fixture providing a mock valid OTP entry."""
    test_otp = "123456"
    hashed_otp = hashlib.sha256(test_otp.encode()).hexdigest()
    expires_at = (datetime.now() + timedelta(minutes=5)).isoformat()
    
    return {
        "email": "test@example.com",
        "otp_hash": hashed_otp,
        "expires_at": expires_at,
        "plain_otp": test_otp  # Added for test convenience
    }


@pytest.fixture(scope="function")
def mock_expired_otp_entry():
    """Fixture providing a mock expired OTP entry."""
    test_otp = "123456"
    hashed_otp = hashlib.sha256(test_otp.encode()).hexdigest()
    expires_at = (datetime.now() - timedelta(minutes=5)).isoformat()
    
    return {
        "email": "test@example.com",
        "otp_hash": hashed_otp,
        "expires_at": expires_at,
        "plain_otp": test_otp  # Added for test convenience
    }


@pytest.fixture(scope="function")
def mock_valid_session_entry():
    """Fixture providing a mock valid session entry."""
    return {
        "email": "test@example.com",
        "token": "valid-session-token-12345",
        "created_at": datetime.now().isoformat()
    }
