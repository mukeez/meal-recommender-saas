import pytest
from app.core.config import settings
from app.tests.constants.user import UserTestConstants
from app.models.referral_tracking import ReferralTrackingResponse, ReferredUser


@pytest.mark.asyncio
class TestReferralTrackingEndpoint:
    """Test class for referral tracking endpoints."""

    async def test_get_referral_tracking_stats_success(
        self, authenticated_client, mock_referral_tracking_service
    ):
        """Test successful retrieval of referral tracking stats."""

        mock_referred_users = [
            ReferredUser(
                id="user_1",
                first_name="John",
                last_name="Doe",
                email="john.doe@example.com",
                date_used="2025-07-25",
            ),
            ReferredUser(
                id="user_2",
                first_name="Jane",
                last_name="Smith",
                email="jane.smith@example.com",
                date_used="2025-07-26",
            ),
        ]

        mock_tracking_response = ReferralTrackingResponse(
            total_users_referred=2, referred_users=mock_referred_users
        )

        mock_referral_tracking_service.get_influencer_tracking_stats.return_value = (
            mock_tracking_response
        )

        response = authenticated_client.get(
            f"{settings.API_V1_STR}/referral-tracking/influencer/{UserTestConstants.MOCK_USER_ID.value}/stats"
        )

        assert response.status_code == 200
        response_data = response.json()

        assert response_data["total_users_referred"] == 2
        assert len(response_data["referred_users"]) == 2
        assert response_data["referred_users"][0]["first_name"] == "John"
        assert response_data["referred_users"][0]["email"] == "john.doe@example.com"
        assert response_data["referred_users"][1]["first_name"] == "Jane"
        assert response_data["referred_users"][1]["email"] == "jane.smith@example.com"

        mock_referral_tracking_service.get_influencer_tracking_stats.assert_called_once_with(
            UserTestConstants.MOCK_USER_ID.value
        )

    async def test_get_referral_tracking_stats_forbidden_access(
        self, authenticated_client
    ):
        """Test accessing another user's referral tracking stats returns 403."""

        different_user_id = "different-user-id-12345"

        response = authenticated_client.get(
            f"{settings.API_V1_STR}/referral-tracking/influencer/{different_user_id}/stats"
        )

        assert response.status_code == 403
        assert (
            "You do not have permission to access this influencer's stats"
            in response.json()["detail"]
        )
