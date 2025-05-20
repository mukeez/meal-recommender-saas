import pytest
from app.core.config import settings
from app.tests.constants.products import MOCK_PRODUCT_SEARCH_DATA


@pytest.mark.asyncio
class TestProductEndpoint:
    async def test_get_products_from_db_success(
        self, authenticated_client, mock_product_get_products
    ):
        """Integration test for successful products search from item logged in db."""

        mock_product_get_products.return_value = MOCK_PRODUCT_SEARCH_DATA

        response = authenticated_client.get(
            f"{settings.API_V1_STR}/products/search", params={"query": "Kallø"}
        )

        assert response.status_code == 200

        assert response.json() == MOCK_PRODUCT_SEARCH_DATA

        mock_product_get_products.assert_called_once_with(
            product_name="Kallø", page=1, page_size=20
        )

    async def test_search_products_from_openfoodfacts_success(
        self,
        authenticated_client,
        mock_product_get_products,
        mock_product_upsert_product,
        mock_openfoodfacts_search,
        mock_products_model,
    ):
        """Integration test for successful products search from openfoodfacts_service."""

        mock_product_get_products.return_value = None

        mock_openfoodfacts_search.return_value = mock_products_model

        response = authenticated_client.get(
            f"{settings.API_V1_STR}/products/search", params={"query": "Kallø"}
        )

        assert response.status_code == 200

        assert response.json()["count"] == MOCK_PRODUCT_SEARCH_DATA["count"]
        assert response.json()["page"] == MOCK_PRODUCT_SEARCH_DATA["page"]
        assert response.json()["page_size"] == MOCK_PRODUCT_SEARCH_DATA["page_size"]

        mock_product_get_products.assert_called_once_with(
            product_name="Kallø", page=1, page_size=20
        )

        mock_openfoodfacts_search.assert_called_once_with(
            product="Kallø", page=1, page_size=20
        )

        mock_product_upsert_product.assert_called_once()
