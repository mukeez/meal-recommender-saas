"""Tests for web search fallback functionality in barcode scanning."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from app.api.endpoints.scan import scan_barcode
from app.services.web_search_service import WebSearchService
from app.services.web_search_llm_service import WebSearchLLMService
from app.models.product import Product, NutritionFacts


@pytest.mark.asyncio
class TestWebSearchFallback:
    """Test web search fallback for barcode scanning."""

    async def test_web_search_fallback_success(self):
        """Test successful web search fallback when database and OpenFoodFacts fail."""
        
        # Mock user authentication
        mock_user = {"id": "test_user", "email": "test@example.com"}
        
        # Mock the services to simulate failures then success
        with patch("app.services.product_service.product_service.scan_barcode", return_value=None), \
             patch("app.services.openfoodfacts_service.openfoodfacts_service.scan_barcode", side_effect=Exception("Not found")), \
             patch("app.services.web_search_service.web_search_service.search_product_by_barcode") as mock_search, \
             patch("app.services.web_search_llm_service.web_search_llm_service.extract_product_from_search_results") as mock_extract, \
             patch("app.services.product_service.product_service.log_product") as mock_log:
            
            # Mock search results
            mock_search_results = [
                {
                    "title": "Test Product - Nutrition Facts",
                    "content": "Test product with 100 calories per 100g, 5g protein, 10g carbs, 2g fat",
                    "url": "https://example.com/product"
                }
            ]
            mock_search.return_value = mock_search_results
            
            # Mock extracted product
            nutrition_facts = NutritionFacts(
                name="Test Product",
                amount=100,
                serving_unit="grams",
                calories=100,
                protein=5.0,
                carbs=10.0,
                fat=2.0
            )
            
            mock_product = Product(
                barcode="1234567890",
                product_name="Test Product",
                brand_name="Test Brand",
                ingredients="Test ingredients"
            )
            mock_product.nutrition_facts = nutrition_facts
            
            mock_extract.return_value = mock_product
            mock_log.return_value = [mock_product]
            
            # Test the endpoint
            response = await scan_barcode("1234567890", mock_user)
            
            # Verify the response
            assert len(response.items) == 1
            assert response.items[0].name == "Test Product"
            assert response.items[0].calories == 100
            assert response.items[0].protein == 5.0
            
            # Verify all services were called
            mock_search.assert_called_once_with("1234567890")
            mock_extract.assert_called_once_with(
                barcode="1234567890",
                search_results=mock_search_results,
                user_id="test@example.com"
            )
            mock_log.assert_called_once()

    async def test_web_search_no_results(self):
        """Test when web search returns no results."""
        
        mock_user = {"id": "test_user", "email": "test@example.com"}
        
        with patch("app.services.product_service.product_service.scan_barcode", return_value=None), \
             patch("app.services.openfoodfacts_service.openfoodfacts_service.scan_barcode", side_effect=Exception("Not found")), \
             patch("app.services.web_search_service.web_search_service.search_product_by_barcode", return_value=None):
            
            # Should raise 404 when all methods fail
            with pytest.raises(HTTPException) as exc_info:
                await scan_barcode("1234567890", mock_user)
            
            assert exc_info.value.status_code == 404
            assert "not found in database, OpenFoodFacts, or web search" in exc_info.value.detail

    async def test_web_search_service_no_api_key(self):
        """Test web search service when API key is not configured."""
        
        # Test without API key
        service = WebSearchService()
        service.api_key = None
        
        result = await service.search_product_by_barcode("1234567890")
        assert result is None

    async def test_web_search_llm_extraction_error(self):
        """Test when LLM extraction fails."""
        
        mock_user = {"id": "test_user", "email": "test@example.com"}
        
        with patch("app.services.product_service.product_service.scan_barcode", return_value=None), \
             patch("app.services.openfoodfacts_service.openfoodfacts_service.scan_barcode", side_effect=Exception("Not found")), \
             patch("app.services.web_search_service.web_search_service.search_product_by_barcode", return_value=[{"title": "test"}]), \
             patch("app.services.web_search_llm_service.web_search_llm_service.extract_product_from_search_results", side_effect=Exception("LLM failed")):
            
            # Should raise 404 when LLM extraction fails
            with pytest.raises(HTTPException) as exc_info:
                await scan_barcode("1234567890", mock_user)
            
            assert exc_info.value.status_code == 404