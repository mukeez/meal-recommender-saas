import pytest
from unittest.mock import AsyncMock


@pytest.fixture(scope="function")
def mock_notification_log_notification(mocker):
    mock = mocker.patch(
        "app.api.endpoints.notifications.notification_service.log_notification",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_notification_get_notifications(mocker):
    mock = mocker.patch(
        "app.api.endpoints.notifications.notification_service.get_notifications",
        new_callable=AsyncMock,
    )
    return mock
