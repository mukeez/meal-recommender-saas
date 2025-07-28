import pytest
from app.core.config import settings
from app.tests.constants.user import UserTestConstants


@pytest.mark.asyncio
class TestReferralCodeEndpoint:
    async def test_generate_referral_code_successfully(
        self, authenticated_client, mock_referral_code_service
    ):
        mock_referral_code_service.save_referral_instance.return_value = "TEST-12345"

        response = authenticated_client.get(
            f"{settings.API_V1_STR}/referral-code/generate",
        )

        assert response.status_code == 201
        mock_referral_code_service.assert_called_once()
