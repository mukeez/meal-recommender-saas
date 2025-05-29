import pytest
from app.core.config import settings
from app.tests.constants.location import MOCK_LOCATION_DATA


@pytest.mark.asyncio
class TestLocationEndpoint:
    async def test_get_location_success(
        self, authenticated_client, mock_location_reverse_geocode
    ):
        """Integration test for successful retrieval of location data."""

        latitude = 5.6066048
        longitude = -0.2064384

        mock_location_reverse_geocode.return_value = MOCK_LOCATION_DATA

        response = authenticated_client.get(
            f"{settings.API_V1_STR}/location/reverse-geocode",
            params={"latitude": latitude, "longitude": longitude},
        )

        assert response.status_code == 200

        assert response.json() == MOCK_LOCATION_DATA

        mock_location_reverse_geocode.assert_called_once_with(
            latitude=latitude, longitude=longitude
        )
