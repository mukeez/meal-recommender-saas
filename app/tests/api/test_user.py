import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.core.config import settings
from app.tests.constants.user import UserTestConstants
from app.models.user import UserProfile
from app.main import app
from io import BytesIO
import httpx


@pytest.mark.asyncio
class TestUserEndpoint:

    async def test_get_user_profile_integration_unauthenticated(self):
        """Integration test for an unauthenticated request using fixtures."""
        from app.api.auth_guard import auth_guard

        async def mock_auth_guard_unauthorized():
            raise HTTPException(status_code=401, detail="Unauthorized")

        app.dependency_overrides[auth_guard] = mock_auth_guard_unauthorized

        try:
            with TestClient(app) as client:
                response = client.get(f"{settings.API_V1_STR}/user/me")

            assert response.status_code == 401

            assert response.json() == {"detail": "Unauthorized"}
        finally:
            # clean up dependency overrides after the test
            app.dependency_overrides = {}

    async def test_get_user_profile_success(
        self,
        authenticated_client,
        mock_user_service_get_profile,
        mock_user_profile_model,
    ):
        """Integration test for successful profile retrieval using fixtures."""
        mock_user_service_get_profile.return_value = mock_user_profile_model

        response = authenticated_client.get(f"{settings.API_V1_STR}/user/me")

        assert response.status_code == 200

        assert response.json() == UserTestConstants.MOCK_USER_PROFILE_DATA.value

        mock_user_service_get_profile.assert_called_once_with(
            user_id=UserTestConstants.MOCK_USER_ID.value
        )

    async def test_update_user_profile_success(
        self,
        authenticated_client,
        mock_user_service_update_profile,
        mock_user_service_upload_avatar,
    ):
        """Integration test for a successful profile update with a valid user avatar"""

        file_content = b"fake document data"
        files = {"avatar": ("document.txt", BytesIO(file_content), "text/plain")}
        updated_profile_data = UserTestConstants.MOCK_USER_PROFILE_DATA.value.copy()
        updated_profile_data["display_name"] = "Itachi"
        updated_profile_data["first_name"] = "Itachi"
        updated_profile_data["last_name"] = "Uchiha"
        updated_profile_data["avatar_url"] = "http://example.com/new_avatar.png"
        mock_user_service_update_profile.return_value = UserProfile(
            **updated_profile_data
        )
        mock_user_service_upload_avatar.return_value = (
            "http://example.com/new_avatar.png"
        )

        form_data = {
            "display_name": "Itachi",
            "first_name": "Itachi",
            "last_name": "Uchiha",
        }

        file_content = b"fake image data"
        files = {"avatar": ("avatar.png", BytesIO(file_content), "image/png")}

        response = authenticated_client.patch(
            f"{settings.API_V1_STR}/user/me",
            data=form_data,
            files=files,
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200

        assert response.json() == updated_profile_data

        # assert update_user_profile called once
        mock_user_service_update_profile.assert_called_once()

        # assert upload_user_avatar called once
        mock_user_service_upload_avatar.assert_called_once()

    async def test_get_user_profile_exception(
        self, authenticated_client, mock_user_service_get_profile
    ):
        """Integration test for handling HTTPException from user_service using fixtures."""
        mock_user_service_get_profile.side_effect = HTTPException(
            status_code=500, detail="Failed to retrieve user profile"
        )

        response = authenticated_client.get(f"{settings.API_V1_STR}/user/me")

        assert response.status_code == 500

        assert response.json() == {"detail": "Failed to retrieve user profile"}

        # assert get_profile called once
        mock_user_service_get_profile.assert_called_once_with(
            user_id=UserTestConstants.MOCK_USER_ID.value
        )

    async def test_update_user_profile_invalid_image_file(
        self,
        authenticated_client,
        mock_user_service_update_profile,
        mock_user_service_upload_avatar,
    ):
        """Integration test for invalid image file(avatar) upload"""

        file_content = b"fake document data"
        files = {"avatar": ("document.txt", BytesIO(file_content), "text/plain")}
        # Use the authenticated client to make the request
        response = authenticated_client.patch(
            f"{settings.API_V1_STR}/user/me",
            files=files,
            headers={"Authorization": "Bearer 12424"},
        )

        # Assert the response status code
        assert response.status_code == 400

        # Assert error detail
        assert response.json() == {"detail": "Only image files allowed."}

        # assert update_user_profile and upload_user_avatar not called
        mock_user_service_update_profile.assert_not_called()
        mock_user_service_upload_avatar.assert_not_called()

    async def test_get_user_preferences(
        self, authenticated_client, mock_user_get_preferences
    ):
        """Integration test for successful user preferences retrieval using fixtures."""
        mock_user_get_preferences.return_value = httpx.Response(
            200, json=[UserTestConstants.MOCK_USER_PREFERENCES_DATA.value]
        )
        response = authenticated_client.get(f"{settings.API_V1_STR}/user/preferences")

        assert response.status_code == 200

        assert response.json() == UserTestConstants.MOCK_USER_PREFERENCES_DATA.value

        mock_user_get_preferences.assert_called_once()

    async def test_patch_user_preferences(
        self, authenticated_client, mock_user_patch_preferences
    ):
        """Integration test for successful user preferences update using fixtures."""

        updated_preferences_data = (
            UserTestConstants.MOCK_USER_PREFERENCES_DATA.value.copy()
        )
        updated_preferences_data["calorie_target"] = 500
        updated_preferences_data["protein_target"] = 170

        mock_user_patch_preferences.return_value = httpx.Response(
            200, json=[updated_preferences_data]
        )

        response = authenticated_client.patch(
            f"{settings.API_V1_STR}/user/preferences",
            json={"calorie_target": 500, "protein_target": 170},
        )

        assert response.status_code == 200

        assert response.json() == updated_preferences_data

        mock_user_patch_preferences.assert_called_once()

    async def test_update_unit_preference(
        self, authenticated_client, mock_user_patch_preferences
    ):
        """Test updating user's unit preference from kg to imperial."""

        updated_preferences_data = UserTestConstants.MOCK_USER_PROFILE_DATA.value.copy()
        updated_preferences_data["unit_preference"] = "imperial"

        mock_user_patch_preferences.return_value = httpx.Response(
            200, json=[updated_preferences_data]
        )

        response = authenticated_client.patch(
            f"{settings.API_V1_STR}/user/me",
            json={"unit_preference": "imperial"},
        )
        
        assert response.status_code == 200
        assert response.json()["unit_preference"] == "imperial"

        mock_user_patch_preferences.assert_called_once()

