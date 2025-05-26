import pytest
from fastapi import HTTPException, status
from app.core.config import settings
from app.tests.constants.user import UserTestConstants
import httpx


@pytest.mark.asyncio
class TestAuthEndpoint:
    async def test_user_login_success(
        self, authenticated_client, mock_auth_httpx_client
    ):
        """Integration test for successful user login."""

        expected_values = {
            "access_token": "eyJhbGciOiJIUzI1",
            "refresh_token": "ttubm5t2ynyr",
            "expires_in": 3600,
            "expires_at": 1747717272,
            "user": {
                "id": UserTestConstants.MOCK_USER_ID.value,
                "email": UserTestConstants.MOCK_USER_EMAIL.value,
            },
        }
        mock_auth_httpx_client.return_value = httpx.Response(200, json=expected_values)

        user_data = {
            "email": UserTestConstants.MOCK_USER_EMAIL.value,
            "password": UserTestConstants.MOCK_USER_PASSWORD.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/login", json=user_data
        )

        assert response.status_code == 200

        assert response.json() == expected_values

        mock_auth_httpx_client.assert_called_once()

    async def test_user_login_failed(
        self, authenticated_client, mock_auth_httpx_client
    ):
        """Integration test for failed user login."""

        mock_auth_httpx_client.side_effect = HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
        )

        user_data = {
            "email": UserTestConstants.MOCK_USER_EMAIL.value,
            "password": UserTestConstants.MOCK_USER_PASSWORD.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/login", json=user_data
        )

        assert response.status_code == 500

        assert response.json() == {"detail": "Login failed"}

        mock_auth_httpx_client.assert_called_once()

    async def test_user_signup_success(
        self, authenticated_client, mock_auth_httpx_client
    ):
        """Integration test for successful user signup."""

        expected_values = {
            "message": "User registered successfully",
            "user": {
                "id": UserTestConstants.MOCK_USER_ID.value,
                "email": UserTestConstants.MOCK_USER_EMAIL.value,
            },
            "session": {},
        }

        mock_auth_httpx_client.return_value = httpx.Response(201, json=expected_values)

        user_data = {
            "email": UserTestConstants.MOCK_USER_EMAIL.value,
            "password": UserTestConstants.MOCK_USER_PASSWORD.value,
            "display_name": UserTestConstants.MOCK_USER_DISPLAY_NAME.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/signup", json=user_data
        )

        assert response.status_code == 201

        assert response.json() == expected_values

        mock_auth_httpx_client.assert_called()

    async def test_user_already_exists(
        self, authenticated_client, mock_auth_httpx_client
    ):
        """Integration test for when a user already exists."""

        expected_values = {
            "msg": "User already registered",
            "error_code": "user_already_exists",
        }

        mock_auth_httpx_client.return_value = httpx.Response(422, json=expected_values)

        user_data = {
            "email": UserTestConstants.MOCK_USER_EMAIL.value,
            "password": UserTestConstants.MOCK_USER_PASSWORD.value,
            "display_name": UserTestConstants.MOCK_USER_DISPLAY_NAME.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/signup", json=user_data
        )

        assert response.status_code == 422

        assert response.json() == {"detail": "User already registered"}

        mock_auth_httpx_client.assert_called()
