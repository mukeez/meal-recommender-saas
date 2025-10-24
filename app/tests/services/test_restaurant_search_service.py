"""Unit tests for unified restaurant search service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.restaurant_search_service import restaurant_search_service
from app.models.meal import SearchFilterRequest
from app.models.scan import CuisineType, DietaryRestriction
from app.tests.constants.filters import (
    MOCK_GOOGLE_PLACES_RESPONSE,
    MOCK_PLACE_DETAILS,
    MOCK_RESTAURANT_PIN
)


@pytest.mark.asyncio
class TestSearchRestaurants:
    """Test base restaurant search functionality."""
    
    async def test_search_restaurants_cache_hit(self, mocker):
        """Test that cached results are returned when available."""
        mock_cache_get = mocker.patch.object(
            restaurant_search_service.cache,
            'get_cached_map_pins',
            new_callable=AsyncMock
        )
        mock_cache_get.return_value = {
            "restaurants": [MOCK_RESTAURANT_PIN],
            "total_count": 1
        }
        
        filters = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278,
            query="pizza"
        )
        
        restaurants, is_cached = await restaurant_search_service.search_restaurants(
            filters=filters,
            user_id="test-user"
        )
        
        assert is_cached is True
        assert len(restaurants) == 1
        assert restaurants[0]["name"] == "Bella Italia"
        mock_cache_get.assert_called_once()
    
    async def test_search_restaurants_cache_miss(self, mocker):
        """Test that Google Places is called on cache miss."""
        # Mock cache miss
        mock_cache_get = mocker.patch.object(
            restaurant_search_service.cache,
            'get_cached_map_pins',
            new_callable=AsyncMock,
            return_value=None
        )
        
        # Mock cache set
        mock_cache_set = mocker.patch.object(
            restaurant_search_service.cache,
            'set_cached_map_pins',
            new_callable=AsyncMock
        )
        
        # Mock Google Places search
        mock_places_search = mocker.patch.object(
            restaurant_search_service.google_places,
            'nearby_search_with_filters',
            new_callable=AsyncMock,
            return_value=MOCK_GOOGLE_PLACES_RESPONSE.copy()
        )
        
        # Mock place details
        mock_place_details = mocker.patch.object(
            restaurant_search_service.google_places,
            'get_place_details',
            new_callable=AsyncMock,
            return_value=MOCK_PLACE_DETAILS.copy()
        )
        
        filters = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278,
            query="pizza"
        )
        
        restaurants, is_cached = await restaurant_search_service.search_restaurants(
            filters=filters,
            user_id="test-user"
        )
        
        assert is_cached is False
        assert len(restaurants) > 0
        mock_cache_get.assert_called_once()
        mock_places_search.assert_called_once()
        mock_cache_set.assert_called_once()
    
    async def test_search_restaurants_with_cuisines(self, mocker):
        """Test search with cuisine filters."""
        mock_cache_get = mocker.patch.object(
            restaurant_search_service.cache,
            'get_cached_map_pins',
            new_callable=AsyncMock,
            return_value=None
        )
        
        mock_cache_set = mocker.patch.object(
            restaurant_search_service.cache,
            'set_cached_map_pins',
            new_callable=AsyncMock
        )
        
        mock_places_search = mocker.patch.object(
            restaurant_search_service.google_places,
            'nearby_search_with_filters',
            new_callable=AsyncMock,
            return_value=MOCK_GOOGLE_PLACES_RESPONSE.copy()
        )
        
        mock_place_details = mocker.patch.object(
            restaurant_search_service.google_places,
            'get_place_details',
            new_callable=AsyncMock,
            return_value=MOCK_PLACE_DETAILS.copy()
        )
        
        filters = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278,
            cuisines=[CuisineType.ITALIAN]
        )
        
        restaurants, is_cached = await restaurant_search_service.search_restaurants(
            filters=filters
        )
        
        # Verify cuisines were passed to Google Places
        call_kwargs = mock_places_search.call_args.kwargs
        assert call_kwargs["cuisines"] == ["italian"]


class TestExtractCuisineTypes:
    """Test cuisine type extraction from Google Places types."""
    
    def test_extract_italian_restaurant(self):
        """Test extraction of Italian cuisine."""
        place_types = ["restaurant", "italian_restaurant", "food"]
        
        cuisines = restaurant_search_service._extract_cuisine_types(place_types)
        
        assert "Italian" in cuisines
    
    def test_extract_multiple_cuisines(self):
        """Test extraction of multiple cuisines."""
        place_types = ["restaurant", "italian_restaurant", "pizza_restaurant", "food"]
        
        cuisines = restaurant_search_service._extract_cuisine_types(place_types)
        
        assert "Italian" in cuisines
        assert "Pizza" in cuisines
    
    def test_extract_no_specific_cuisine(self):
        """Test fallback when no specific cuisine type."""
        place_types = ["restaurant", "food", "establishment"]
        
        cuisines = restaurant_search_service._extract_cuisine_types(place_types)
        
        assert cuisines == ["Restaurant"]


class TestCalculateDistance:
    """Test distance calculation using Haversine formula."""
    
    def test_calculate_distance_same_point(self):
        """Test distance calculation for same coordinates."""
        distance = restaurant_search_service._calculate_distance(
            51.5074, -0.1278,
            51.5074, -0.1278
        )
        
        assert distance == 0.0
    
    def test_calculate_distance_known_points(self):
        """Test distance calculation between known points."""
        # London to nearby point (~1km)
        distance = restaurant_search_service._calculate_distance(
            51.5074, -0.1278,  # Central London
            51.5080, -0.1285   # Nearby point
        )
        
        # Should be less than 1km
        assert distance is not None
        assert 0 < distance < 1.0
    
    def test_calculate_distance_none_coordinates(self):
        """Test handling of None coordinates."""
        distance = restaurant_search_service._calculate_distance(
            51.5074, -0.1278,
            None, None
        )
        
        assert distance is None


class TestGetFirstPhotoUrl:
    """Test photo URL extraction."""
    
    def test_get_photo_url_with_photos(self):
        """Test getting photo URL when photos exist."""
        photos = [
            {"photo_reference": "test_ref_1"},
            {"photo_reference": "test_ref_2"}
        ]
        
        url = restaurant_search_service._get_first_photo_url(photos)
        
        assert url is not None
        assert "test_ref_1" in url
    
    def test_get_photo_url_empty_list(self):
        """Test handling of empty photo list."""
        url = restaurant_search_service._get_first_photo_url([])
        
        assert url is None
    
    def test_get_photo_url_none(self):
        """Test handling of None photos."""
        url = restaurant_search_service._get_first_photo_url(None)
        
        assert url is None


@pytest.mark.asyncio
class TestSearchWithMealRecommendations:
    """Test restaurant search with meal generation."""
    
    async def test_search_with_meals_adds_recommendations(self, mocker):
        """Test that meal recommendations are added to restaurants."""
        # Mock base search
        mock_search = mocker.patch.object(
            restaurant_search_service,
            'search_restaurants',
            new_callable=AsyncMock,
            return_value=([{
                "id": "place_1",
                "name": "Test Restaurant",
                "cuisine_types": ["Italian"]
            }], False)
        )
        
        # Mock meal generation - use actual method name
        mock_generate_meals = mocker.patch.object(
            restaurant_search_service.meal_matcher,
            'get_top_meal_for_restaurant',
            new_callable=AsyncMock,
            return_value={
                "name": "Margherita Pizza",
                "match_score": 85,
                "macros": {"calories": 580, "protein": 25, "carbs": 70, "fat": 18}
            }
        )
        
        filters = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278,
            query="pizza",
            calories=600
        )
        
        restaurants, is_cached = await restaurant_search_service.search_with_meal_recommendations(
            filters=filters,
            user_id="test-user"
        )
        
        assert len(restaurants) == 1
        assert "meals" in restaurants[0]
        assert "top_meal" in restaurants[0]
        assert restaurants[0]["top_meal"]["name"] == "Margherita Pizza"
        mock_generate_meals.assert_called_once()
    
    async def test_search_with_meals_filters_by_meal_name(self, mocker):
        """Test that meals are filtered by meal_name when specified."""
        # Mock base search
        mock_search = mocker.patch.object(
            restaurant_search_service,
            'search_restaurants',
            new_callable=AsyncMock,
            return_value=([{
                "id": "place_1",
                "name": "Test Restaurant",
                "cuisine_types": ["Italian"]
            }], False)
        )
        
        # Mock meal generation
        mock_generate_meal = mocker.patch.object(
            restaurant_search_service.meal_matcher,
            'get_top_meal_for_restaurant',
            new_callable=AsyncMock,
            return_value={"name": "Margherita Pizza", "match_score": 85}
        )
        
        # Mock meal name filter
        mock_filter = mocker.patch.object(
            restaurant_search_service.meal_matcher,
            'filter_by_meal_name',
            return_value=True
        )
        
        filters = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278,
            meal_name="pizza"
        )
        
        restaurants, is_cached = await restaurant_search_service.search_with_meal_recommendations(
            filters=filters
        )
        
        # Should have meals
        assert len(restaurants) == 1
        assert "meals" in restaurants[0]
    
    async def test_search_with_meals_handles_generation_error(self, mocker):
        """Test that meal generation errors are handled gracefully."""
        # Mock base search
        mock_search = mocker.patch.object(
            restaurant_search_service,
            'search_restaurants',
            new_callable=AsyncMock,
            return_value=([{
                "id": "place_1",
                "name": "Test Restaurant",
                "cuisine_types": ["Italian"]
            }], False)
        )
        
        # Mock meal generation to raise error
        mock_generate_meal = mocker.patch.object(
            restaurant_search_service.meal_matcher,
            'get_top_meal_for_restaurant',
            new_callable=AsyncMock,
            side_effect=Exception("Meal generation failed")
        )
        
        filters = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278
        )
        
        restaurants, is_cached = await restaurant_search_service.search_with_meal_recommendations(
            filters=filters
        )
        
        # Should still return restaurant but with empty meals
        assert len(restaurants) == 1
        assert restaurants[0]["meals"] == []
        assert restaurants[0]["top_meal"] is None


@pytest.mark.asyncio
class TestCacheKeyGeneration:
    """Test unified cache key generation."""
    
    async def test_same_filters_same_cache_key(self, mocker):
        """Test that identical filters generate the same cache key."""
        mock_cache_get = mocker.patch.object(
            restaurant_search_service.cache,
            'get_cached_map_pins',
            new_callable=AsyncMock,
            return_value={"restaurants": []}
        )
        
        filters1 = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278,
            query="pizza",
            cuisines=[CuisineType.ITALIAN]
        )
        
        filters2 = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278,
            query="pizza",
            cuisines=[CuisineType.ITALIAN]
        )
        
        await restaurant_search_service.search_restaurants(filters1, user_id="user1")
        cache_key_1 = mock_cache_get.call_args[0][0]
        
        mock_cache_get.reset_mock()
        
        await restaurant_search_service.search_restaurants(filters2, user_id="user1")
        cache_key_2 = mock_cache_get.call_args[0][0]
        
        # Same filters should produce same cache key
        assert cache_key_1 == cache_key_2
    
    async def test_different_view_types_different_cache_keys(self, mocker):
        """Test that different view types generate different cache keys."""
        mock_cache_get = mocker.patch.object(
            restaurant_search_service.cache,
            'get_cached_map_pins',
            new_callable=AsyncMock,
            return_value={"restaurants": []}
        )
        
        filters = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278,
            query="pizza"
        )
        
        await restaurant_search_service.search_restaurants(
            filters, user_id="user1", view_type="list"
        )
        cache_key_list = mock_cache_get.call_args[0][0]
        
        mock_cache_get.reset_mock()
        
        await restaurant_search_service.search_restaurants(
            filters, user_id="user1", view_type="map"
        )
        cache_key_map = mock_cache_get.call_args[0][0]
        
        # Different view types should have different cache keys
        assert cache_key_list != cache_key_map
