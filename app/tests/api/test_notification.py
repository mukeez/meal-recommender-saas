import pytest
from app.core.config import settings


@pytest.mark.asyncio
class TestNotificationsEndpoint:
    async def test_log_notification_success(
        self, authenticated_client, mock_notification_log_notification
    ):
        expected_values = {
            "message": "Notification logged successfully",
        }

        notification_data = {
            "type": "system",
            "title": "Hello",
            "body": "World!",
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/notifications", json=notification_data
        )

        assert response.status_code == 201
        assert response.json() == expected_values

        mock_notification_log_notification.assert_called_once()

    async def test_get_user_notifications_success(
        self, authenticated_client, mock_notification_get_notifications
    ):
        authenticated_client.post(
            f"{settings.API_V1_STR}/notifications",
            json={
                "type": "system",
                "title": "Hello",
                "body": "World!",
            },
        )

        response = authenticated_client.get(f"{settings.API_V1_STR}/notifications")
        mock_notification_get_notifications.assert_called_once()

    async def test_mark_notification_as_read_success(
        self, authenticated_client, mock_notification_mark_notification_as_read
    ):
        notification_id = "test-notification-id"
        response = authenticated_client.patch(
            f"{settings.API_V1_STR}/notifications/{notification_id}/read",
            json={"status": "read"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "message": "Notification status updated successfully"
        }

        mock_notification_mark_notification_as_read.assert_called_once()
