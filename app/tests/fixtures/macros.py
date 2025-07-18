import pytest


@pytest.fixture(scope="function")
def mock_save_user_preferences(mocker):
    """Fixture to patch and provide a mock for macros_service.save_user_preferences."""
    mock = mocker.patch(
        "app.services.macros_service.macros_service.save_user_preferences",
        return_value={"id": "123", "user_id": "test-user"}
    )
    return mock

@pytest.fixture(scope="function")
def mock_macros_update_user_profile(mocker):
    """Fixture to patch and provide a mock for macros_service.update_user_profile."""
    mock = mocker.patch(
        "app.api.endpoints.macros.user_service.update_user_profile",
        return_value={"id": "123", "user_id": "test-user"}
    )
    return mock