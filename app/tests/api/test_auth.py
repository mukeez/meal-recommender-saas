import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from app.core.config import settings
from app.tests.constants.user import UserTestConstants
from app.tests.constants.otp import OTPTestConstants, get_valid_otp_entry, get_expired_otp_entry, get_session_token_entry
from app.main import app
import httpx


@pytest.mark.asyncio
class TestAuthEndpoint:
    # Keep the existing login and signup tests
    async def test_user_login_success(
        self, authenticated_client, mock_auth_httpx_client_post
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
        mock_auth_httpx_client_post.return_value = httpx.Response(200, json=expected_values)

        user_data = {
            "email": UserTestConstants.MOCK_USER_EMAIL.value,
            "password": UserTestConstants.MOCK_USER_PASSWORD.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/login", json=user_data
        )

        assert response.status_code == 200
        assert response.json() == expected_values
        mock_auth_httpx_client_post.assert_called_once()

    async def test_user_login_failed(
        self, authenticated_client, mock_auth_httpx_client_post
    ):
        """Integration test for failed user login."""

        mock_auth_httpx_client_post.side_effect = HTTPException(
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
        mock_auth_httpx_client_post.assert_called_once()

    async def test_user_signup_success(
        self, authenticated_client, mock_auth_httpx_client_post
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

        mock_auth_httpx_client_post.return_value = httpx.Response(201, json=expected_values)

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
        mock_auth_httpx_client_post.assert_called()

    async def test_user_already_exists(
        self, authenticated_client, mock_auth_httpx_client_post
    ):
        """Integration test for when a user already exists."""

        expected_values = {
            "msg": "User already registered",
            "error_code": "user_already_exists",
        }

        mock_auth_httpx_client_post.return_value = httpx.Response(422, json=expected_values)

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
        mock_auth_httpx_client_post.assert_called()

    
    async def test_forgot_password_success(
        self, authenticated_client, mock_user_service, mock_mail_service
    ):
        """Test successful OTP generation for password reset."""

        # Configure user service mock to find user
        mock_user_service.get_user_by_email.return_value = {
            "id": UserTestConstants.MOCK_USER_ID.value,
            "email": UserTestConstants.MOCK_USER_EMAIL.value,
        }

        # Make request
        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/forgot-password",
            json={"email": UserTestConstants.MOCK_USER_EMAIL.value},
        )

        assert response.status_code == 200
        assert response.json() == {
            "message": "An OTP has been sent to your mail."
        }

        # Verify method calls
        mock_user_service.get_user_by_email.assert_called_once_with(
            UserTestConstants.MOCK_USER_EMAIL.value
        )
        mock_user_service.store_otp.assert_called_once()
        mock_mail_service.send_email.assert_called_once()
        
        # Verify email parameters
        send_email_args = mock_mail_service.send_email.call_args[1]
        assert send_email_args["recipient"] == UserTestConstants.MOCK_USER_EMAIL.value
        assert send_email_args["subject"] == "Password Reset OTP"
        assert send_email_args["template_name"] == "otp.html"
        assert "otp_code" in send_email_args["context"]

    async def test_forgot_password_nonexistent_user(
        self, authenticated_client, mock_user_service, mock_mail_service
    ):
        """Test OTP request for non-existent user."""

        mock_user_service.get_user_by_email.return_value = None

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )

        # Should still return 200 to prevent email enumeration
        assert response.status_code == 200
        assert response.json() == {
            "message": "An OTP has been sent to your mail."
        }

        # Verify user was looked up but no OTP was stored
        mock_user_service.get_user_by_email.assert_called_once_with(
            "nonexistent@example.com"
        )
        mock_user_service.store_otp.assert_not_called()
        mock_mail_service.send_email.assert_not_called()

    async def test_verify_otp_success(
        self, authenticated_client, mock_user_service
    ):
        """Test successful OTP verification."""

        otp_entry = get_valid_otp_entry(UserTestConstants.MOCK_USER_EMAIL.value)
        mock_user_service.get_otp.return_value = otp_entry

        # Make request
        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/verify-otp",
            json={
                "email": UserTestConstants.MOCK_USER_EMAIL.value,
                "otp": OTPTestConstants.MOCK_OTP.value,
            },
        )

        assert response.status_code == 200
        response_data = response.json()
        assert "message" in response_data
        assert "session_token" in response_data
        assert response_data["message"] == "OTP verified."

        # Verify session token was stored
        mock_user_service.store_session_token.assert_called_once()
        call_args = mock_user_service.store_session_token.call_args
        assert call_args[0][0] == UserTestConstants.MOCK_USER_EMAIL.value
        assert isinstance(call_args[0][1], str)

    async def test_verify_otp_expired(
        self, authenticated_client, mock_user_service
    ):
        """Test OTP verification with expired OTP."""
        otp_entry = get_expired_otp_entry(UserTestConstants.MOCK_USER_EMAIL.value)
        mock_user_service.get_otp.return_value = otp_entry

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/verify-otp",
            json={
                "email": UserTestConstants.MOCK_USER_EMAIL.value,
                "otp": OTPTestConstants.MOCK_OTP.value,
            },
        )

        assert response.status_code == 400
        assert "Expired OTP" in response.json()["detail"]

        # Verify session token was not stored
        mock_user_service.store_session_token.assert_not_called()

    async def test_verify_otp_incorrect(
        self, authenticated_client, mock_user_service
    ):
        """Test OTP verification with incorrect OTP."""

        # Configure mock to return valid OTP data
        otp_entry = get_valid_otp_entry(UserTestConstants.MOCK_USER_EMAIL.value)
        mock_user_service.get_otp.return_value = otp_entry

        # Make request with wrong OTP
        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/verify-otp",
            json={
                "email": UserTestConstants.MOCK_USER_EMAIL.value,
                "otp": "654321",  # Wrong OTP
            },
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid OTP."}

        # Verify session token was not stored
        mock_user_service.store_session_token.assert_not_called()

    async def test_verify_otp_not_found(
        self, authenticated_client, mock_user_service
    ):
        """Test OTP verification with no OTP found."""

    
        mock_user_service.get_otp.return_value = None

        # Make request
        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/verify-otp",
            json={
                "email": UserTestConstants.MOCK_USER_EMAIL.value,
                "otp": OTPTestConstants.MOCK_OTP.value,
            },
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid or expired OTP."}

        # Verify session token was not stored
        mock_user_service.store_session_token.assert_not_called()

    async def test_reset_password_success(
        self, authenticated_client, mock_user_service
    ):
        """Test successful password reset."""

        # Configure mock to return valid session token
        session_entry = get_session_token_entry(UserTestConstants.MOCK_USER_EMAIL.value)
        mock_user_service.get_session_token.return_value = session_entry

        # Make request
        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/reset-password",
            json={
                "email": UserTestConstants.MOCK_USER_EMAIL.value,
                "new_password": OTPTestConstants.MOCK_NEW_PASSWORD.value,
                "session_token": OTPTestConstants.MOCK_SESSION_TOKEN.value,
            },
        )

        assert response.status_code == 200
        assert response.json() == {"message": "Password reset successful."}

        # Verify password was updated and tokens were invalidated
        mock_user_service.update_password.assert_called_once()
        mock_user_service.invalidate_otp.assert_called_once_with(
            UserTestConstants.MOCK_USER_EMAIL.value
        )
        mock_user_service.invalidate_session_token.assert_called_once_with(
            UserTestConstants.MOCK_USER_EMAIL.value
        )

    async def test_reset_password_invalid_token(
        self, authenticated_client, mock_user_service
    ):
        """Test password reset with invalid token."""

        # Configure mock to return valid session entry
        session_entry = get_session_token_entry(UserTestConstants.MOCK_USER_EMAIL.value)
        mock_user_service.get_session_token.return_value = session_entry

        # Make request with incorrect token
        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/reset-password",
            json={
                "email": UserTestConstants.MOCK_USER_EMAIL.value,
                "new_password": OTPTestConstants.MOCK_NEW_PASSWORD.value,
                "session_token": OTPTestConstants.MOCK_INVALID_SESSION_TOKEN.value,
            },
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid session token."}

        # Verify password was not updated
        mock_user_service.update_password.assert_not_called()
        mock_user_service.invalidate_otp.assert_not_called()
        mock_user_service.invalidate_session_token.assert_not_called()

    async def test_reset_password_no_session(
        self, authenticated_client, mock_user_service
    ):
        """Test password reset with no session found."""

        # Configure mock to return no session entry
        mock_user_service.get_session_token.return_value = None

        # Make request
        response = authenticated_client.post(
            f"{settings.API_V1_STR}/auth/reset-password",
            json={
                "email": UserTestConstants.MOCK_USER_EMAIL.value,
                "new_password": OTPTestConstants.MOCK_NEW_PASSWORD.value,
                "session_token": OTPTestConstants.MOCK_SESSION_TOKEN.value,
            },
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid session token."}

        # Verify password was not updated
        mock_user_service.update_password.assert_not_called()
        mock_user_service.invalidate_otp.assert_not_called()
        mock_user_service.invalidate_session_token.assert_not_called()

    async def test_change_password_success(
        self, authenticated_client, mock_auth_httpx_client_put
    ):
        """Test successful authenticated password change."""

        expected_values = {"message": "Password change successful"}

        # Mock the httpx response
        mock_auth_httpx_client_put.return_value = httpx.Response(200, json=expected_values)

        # Make request with proper Authorization header
        response = authenticated_client.patch(
            f"{settings.API_V1_STR}/auth/change-password",
            json={"password": "NewSecureP@ssw0rd"},
            headers={"Authorization": "Bearer test-token"}
        )

        assert response.status_code == 200
        assert response.json() == expected_values
        mock_auth_httpx_client_put.assert_called_once()

    async def test_change_password_unauthenticated(self):
        """Test password change without authentication."""

        from app.api.auth_guard import auth_guard

        async def mock_auth_guard_unauthorized():
            raise HTTPException(status_code=401, detail="Unauthorized")

        app.dependency_overrides[auth_guard] = mock_auth_guard_unauthorized

        try:
            with TestClient(app) as client:
                response = client.patch(
                    f"{settings.API_V1_STR}/auth/change-password",
                    json={"password": "NewSecureP@ssw0rd"},
                    headers={"Authorization": "Bearer test-token"}
                )


            assert response.status_code == 401

            assert response.json() == {"detail": "Unauthorized"}
        finally:
            # clean up dependency overrides after the test
            app.dependency_overrides = {}
