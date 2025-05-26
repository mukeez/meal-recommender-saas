import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock
from app.tests.constants.scan import ScanTestConstants
from app.tests.constants.products import MOCK_PRODUCT_SEARCH_DATA


@pytest.fixture(scope="function")
def mock_location_reverse_geocode(mocker):
    """Fixture to patch and provide a mock for location_service.reverse_geocode."""
    mock = mocker.patch(
        "app.api.endpoints.location.location_service.reverse_geocode",
        new_callable=AsyncMock,
    )
    return mock
