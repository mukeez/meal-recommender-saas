import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock
from app.tests.constants.scan import ScanTestConstants
from app.tests.constants.products import MOCK_PRODUCT_SEARCH_DATA


@pytest.fixture(scope="function")
def mock_product_get_products(mocker):
    """Fixture to patch and provide a mock for product_service.get_products."""
    mock = mocker.patch(
        "app.api.endpoints.products.product_service.get_products",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_product_upsert_product(mocker):
    """Fixture to patch and provide a mock for product_service.upsert_product."""
    mock = mocker.patch(
        "app.api.endpoints.products.product_service.upsert_product",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_openfoodfacts_search(mocker):
    """Fixture to patch and provide a mock for openfoodfacts_service.product_search."""
    mock = mocker.patch(
        "app.api.endpoints.products.openfoodfacts_service.product_search",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_products_model():
    """Fixture providing a mock LoggedProducts model instance."""
    from app.models.product import ProductList, Product

    return ProductList(
        products=[Product(**ScanTestConstants.PRODUCT_DATA.value)],
        page=1,
        page_size=20,
        count=1,
    )
