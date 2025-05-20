import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock
from app.tests.constants.user import UserTestConstants


@pytest.fixture(scope="function")
def mock_user_service_get_profile(mocker):
    """Fixture to patch and provide a mock for user_service.get_user_profile."""
    mock = mocker.patch(
        "app.api.endpoints.user.user_service.get_user_profile", new_callable=AsyncMock
    )
    return mock


@pytest.fixture(scope="function")
def mock_user_service_update_profile(mocker):
    """Fixture to patch and provide a mock for user_service.update_user_profile."""
    mock = mocker.patch(
        "app.api.endpoints.user.user_service.update_user_profile",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_user_get_preferences(mocker):
    """Fixture to patch and provide a mock for retrieving user preferences."""
    mock = mocker.patch("app.api.endpoints.user.httpx.AsyncClient.get")
    return mock


@pytest.fixture(scope="function")
def mock_user_patch_preferences(mocker):
    """Fixture to patch and provide a mock for patching user preferences."""
    mock = mocker.patch("app.api.endpoints.user.httpx.AsyncClient.patch")
    return mock


@pytest.fixture(scope="function")
def mock_user_service_upload_avatar(mocker):
    """Fixture to patch and provide a mock for user_service.upload_user_avatar."""
    mock = mocker.patch(
        "app.api.endpoints.user.user_service.upload_user_avatar", new_callable=AsyncMock
    )
    return mock


@pytest.fixture(scope="function")
def mock_user_profile_model():
    """Fixture providing a mock UserProfile model instance."""
    from app.models.user import UserProfile

    return UserProfile(**UserTestConstants.MOCK_USER_PROFILE_DATA.value)
