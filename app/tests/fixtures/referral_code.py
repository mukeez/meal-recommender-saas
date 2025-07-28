import pytest
from unittest.mock import AsyncMock


@pytest.fixture(scope="function")
def mock_referral_code_service(mocker):
    mock = mocker.patch(
        "app.api.endpoints.referral_code.referral_code_service.save_referral_instance",
        new_callable=AsyncMock,
    )
    return mock
