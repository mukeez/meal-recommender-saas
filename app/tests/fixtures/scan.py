import pytest
from unittest.mock import AsyncMock
from app.tests.constants.scan import ScanTestConstants


@pytest.fixture(scope="function")
def mock_product_scan_barcode(mocker):
    """Fixture to patch and provide a mock for product_service.scan_barcode."""
    mock = mocker.patch(
        "app.api.endpoints.scan.product_service.scan_barcode", new_callable=AsyncMock
    )
    return mock


@pytest.fixture(scope="function")
def mock_product_log_product(mocker):
    """Fixture to patch and provide a mock for product_service.log_product."""
    mock = mocker.patch(
        "app.api.endpoints.scan.product_service.log_product", new_callable=AsyncMock
    )
    return mock


@pytest.fixture(scope="function")
def mock_openfoodfacts_scan_barcode(mocker):
    """Fixture to patch and provide a mock for openfoodfacts_service.scan_barcode."""
    mock = mocker.patch(
        "app.api.endpoints.scan.openfoodfacts_service.scan_barcode",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_logged_products_model():
    """Fixture providing a mock LoggedProducts model instance."""
    from app.models.product import LoggedProduct

    return LoggedProduct(**ScanTestConstants.PRODUCT_DATA.value)


@pytest.fixture(scope="function")
def mock_scan_image_ai(mocker):
    """Fixture to patch and provide a mock meal vision ai service."""
    mock = mocker.patch("app.api.endpoints.scan.httpx.AsyncClient.post")
    return mock


@pytest.fixture(scope="function")
def mock_scan_encoded_image(mocker):
    """Fixture to patch and provide a mock meal vision ai service."""
    mock = mocker.patch("app.api.endpoints.scan.base64.b64encode")
    return mock
