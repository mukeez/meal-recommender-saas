"""Unit tests for Google Places service with filter support."""


import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.google_places_service import google_places_service, GooglePlacesAPIError
from app.tests.constants.filters import (
    MOCK_GOOGLE_PLACES_RESPONSE,
    MOCK_PLACE_DETAILS
)


class TestBuildSearchKeyword:
    """Test search keyword building from filters."""
    
    def test_build_keyword_restaurant_name_priority(self):
        """Test that restaurant_name has highest priority."""
        keyword = google_places_service._build_search_keyword(
            query="pizza",
            meal_name="margherita",
            restaurant_name="bella italia",
            cuisines=["italian"]
        )
        
        assert keyword == "bella italia"
    
    def test_build_keyword_query_priority(self):
        """Test that query has second priority."""
        keyword = google_places_service._build_search_keyword(
            query="pizza",
            meal_name="margherita",
            cuisines=["italian"]
        )
        
        assert keyword == "pizza"
    
    def test_build_keyword_meal_with_cuisines(self):
        """Test building keyword from meal_name and cuisines."""
        keyword = google_places_service._build_search_keyword(
            meal_name="margherita",
            cuisines=["italian", "mexican"]
        )
        
        assert "margherita" in keyword
        assert "italian" in keyword
        assert "mexican" in keyword
    
    def test_build_keyword_cuisines_only(self):
        """Test building keyword from cuisines only."""
        keyword = google_places_service._build_search_keyword(
            cuisines=["italian", "chinese"]
        )
        
        assert "italian" in keyword
        assert "chinese" in keyword
    
    def test_build_keyword_none_when_empty(self):
        """Test that None is returned when no filters provided."""
        keyword = google_places_service._build_search_keyword()
        assert keyword is None


class TestFilterByCuisine:
    """Test cuisine filtering."""
    
    def test_filter_by_single_cuisine(self):
        """Test filtering by single cuisine type."""
        places = MOCK_GOOGLE_PLACES_RESPONSE.copy()
        cuisines = ["italian"]
        
        result = google_places_service._filter_by_cuisine(places, cuisines)
        
        assert len(result) == 1
        assert result[0]["name"] == "Bella Italia"
    
    def test_filter_by_multiple_cuisines(self):
        """Test filtering by multiple cuisine types."""
        places = MOCK_GOOGLE_PLACES_RESPONSE.copy()
        cuisines = ["italian", "mexican"]
        
        result = google_places_service._filter_by_cuisine(places, cuisines)
        
        assert len(result) == 2
        assert any(p["name"] == "Bella Italia" for p in result)
        assert any(p["name"] == "Taco Bell" for p in result)
    
    def test_filter_no_matches(self):
        """Test filtering when no places match cuisine."""
        places = MOCK_GOOGLE_PLACES_RESPONSE.copy()
        cuisines = ["japanese"]
        
        result = google_places_service._filter_by_cuisine(places, cuisines)
        
        assert len(result) == 0
    
    def test_filter_none_cuisines(self):
        """Test that None cuisines returns all places."""
        places = MOCK_GOOGLE_PLACES_RESPONSE.copy()
        
        result = google_places_service._filter_by_cuisine(places, None)
        
        assert len(result) == len(places)
    
    def test_filter_empty_cuisines(self):
        """Test that empty cuisines list returns all places."""
        places = MOCK_GOOGLE_PLACES_RESPONSE.copy()
        
        result = google_places_service._filter_by_cuisine(places, [])
        
        assert len(result) == len(places)


class TestExtractMenuUrl:
    """Test menu URL extraction."""
    
    def test_extract_menu_url_with_menu_keyword(self):
        """Test extraction when website contains 'menu'."""
        place_details = {
            "website": "https://restaurant.com/menu"
        }
        
        url = google_places_service.extract_menu_url(place_details)
        
        assert url == "https://restaurant.com/menu"
    
    def test_extract_menu_url_with_order_keyword(self):
        """Test extraction when website contains 'order'."""
        place_details = {
            "website": "https://restaurant.com/order-online"
        }
        
        url = google_places_service.extract_menu_url(place_details)
        
        assert url == "https://restaurant.com/order-online"
    
    def test_extract_menu_url_generic_website(self):
        """Test extraction with generic website."""
        place_details = {
            "website": "https://restaurant.com"
        }
        
        url = google_places_service.extract_menu_url(place_details)
        
        assert url == "https://restaurant.com"
    
    def test_extract_menu_url_no_website(self):
        """Test extraction when no website field."""
        place_details = {}
        
        url = google_places_service.extract_menu_url(place_details)
        
        assert url is None


@pytest.mark.asyncio
class TestNearbySearchWithFilters:
    """Test nearby search with unified filter support."""
    
    async def test_nearby_search_with_all_filters(self, mocker):
        """Test nearby search with all filter types."""
        mock_nearby_search = mocker.patch.object(
            google_places_service,
            'nearby_search',
            new_callable=AsyncMock
        )
        mock_nearby_search.return_value = MOCK_GOOGLE_PLACES_RESPONSE.copy()
        
        result = await google_places_service.nearby_search_with_filters(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5000,
            query="pizza",
            meal_name="margherita",
            restaurant_name="bella italia",
            cuisines=["italian"]
        )
        
        # Should call nearby_search with restaurant_name (highest priority)
        mock_nearby_search.assert_called_once()
        call_kwargs = mock_nearby_search.call_args.kwargs
        assert call_kwargs["keyword"] == "bella italia"
        
        # Should filter results by cuisine
        assert len(result) == 1
        assert result[0]["name"] == "Bella Italia"
    
    async def test_nearby_search_with_cuisine_filter(self, mocker):
        """Test nearby search filters by cuisine."""
        mock_nearby_search = mocker.patch.object(
            google_places_service,
            'nearby_search',
            new_callable=AsyncMock
        )
        mock_nearby_search.return_value = MOCK_GOOGLE_PLACES_RESPONSE.copy()
        
        result = await google_places_service.nearby_search_with_filters(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5000,
            cuisines=["italian"]
        )
        
        # Should filter to only Italian restaurant
        assert len(result) == 1
        assert result[0]["name"] == "Bella Italia"
    
    async def test_nearby_search_without_filters(self, mocker):
        """Test nearby search without any filters."""
        mock_nearby_search = mocker.patch.object(
            google_places_service,
            'nearby_search',
            new_callable=AsyncMock
        )
        mock_nearby_search.return_value = MOCK_GOOGLE_PLACES_RESPONSE.copy()
        
        result = await google_places_service.nearby_search_with_filters(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5000
        )
        
        # Should return all results
        assert len(result) == 2
        mock_nearby_search.assert_called_once_with(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5000,
            keyword=None,
            place_type="restaurant"
        )


class TestGetPhotoUrl:
    """Test photo URL generation."""
    
    def test_get_photo_url_default_width(self):
        """Test photo URL generation with default width."""
        url = google_places_service.get_photo_url("photo_ref_123")
        
        assert "photo_ref_123" in url
        assert "maxwidth=400" in url
    
    def test_get_photo_url_custom_width(self):
        """Test photo URL generation with custom width."""
        url = google_places_service.get_photo_url("photo_ref_123", max_width=800)
        
        assert "photo_ref_123" in url
        assert "maxwidth=800" in url
