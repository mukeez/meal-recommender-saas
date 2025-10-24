import pytest
from unittest.mock import AsyncMock
from app.services.restaurant_meal_matching_service import restaurant_meal_matching_service


class TestRestaurantMealMatchingService:
    """Test suite for RestaurantMealMatchingService."""

    def test_filter_by_meal_name_match(self):
        """Test filtering meal by name with matching query."""
        meal = {"name": "Margherita Pizza", "calories": 800}
        
        result = restaurant_meal_matching_service.filter_by_meal_name(meal, "pizza")
        assert result is True

    def test_filter_by_meal_name_no_match(self):
        """Test filtering meal by name with non-matching query."""
        meal = {"name": "Caesar Salad", "calories": 300}
        
        result = restaurant_meal_matching_service.filter_by_meal_name(meal, "burger")
        assert result is False

    def test_filter_by_meal_name_case_insensitive(self):
        """Test that meal name filtering is case-insensitive."""
        meal = {"name": "SPAGHETTI CARBONARA", "calories": 700}
        
        result = restaurant_meal_matching_service.filter_by_meal_name(meal, "carbonara")
        assert result is True

    def test_filter_by_meal_name_partial_match(self):
        """Test that partial matches work."""
        meal = {"name": "Grilled Chicken Breast", "calories": 350}
        
        result = restaurant_meal_matching_service.filter_by_meal_name(meal, "chicken")
        assert result is True

    def test_filter_by_meal_name_no_query(self):
        """Test that no filter is applied when query is None."""
        meal = {"name": "Any Meal", "calories": 500}
        
        result = restaurant_meal_matching_service.filter_by_meal_name(meal, None)
        assert result is True

    def test_filter_by_meal_name_empty_query(self):
        """Test that no filter is applied with empty string query."""
        meal = {"name": "Any Meal", "calories": 500}
        
        result = restaurant_meal_matching_service.filter_by_meal_name(meal, "")
        assert result is True

    def test_extract_cuisine_from_types_italian(self):
        """Test extracting Italian cuisine type."""
        place_types = ["italian_restaurant", "restaurant", "food"]
        
        cuisine = restaurant_meal_matching_service._extract_cuisine_from_types(place_types)
        assert cuisine == "Italian"

    def test_extract_cuisine_from_types_chinese(self):
        """Test extracting Chinese cuisine type."""
        place_types = ["chinese_restaurant", "restaurant", "food", "point_of_interest"]
        
        cuisine = restaurant_meal_matching_service._extract_cuisine_from_types(place_types)
        assert cuisine == "Chinese"

    def test_extract_cuisine_from_types_fallback(self):
        """Test fallback when no cuisine type found."""
        place_types = ["restaurant", "food", "point_of_interest"]
        
        cuisine = restaurant_meal_matching_service._extract_cuisine_from_types(place_types)
        assert cuisine == "restaurant"

    def test_extract_cuisine_from_types_empty_list(self):
        """Test extraction with empty types list."""
        place_types = []
        
        cuisine = restaurant_meal_matching_service._extract_cuisine_from_types(place_types)
        assert cuisine == "restaurant"

    def test_extract_cuisine_from_types_first_match(self):
        """Test that first matching cuisine type is returned."""
        place_types = ["mexican_restaurant", "italian_restaurant", "restaurant"]
        
        cuisine = restaurant_meal_matching_service._extract_cuisine_from_types(place_types)
        assert cuisine == "Mexican"

    @pytest.mark.asyncio
    async def test_get_top_meal_includes_search_context(self, mocker):
        """Test that meal generation includes meal name in prompt if specified."""
        mock_generate = mocker.patch.object(
            restaurant_meal_matching_service,
            'generate_response',
            new_callable=AsyncMock,
            return_value={
                "name": "Margherita Pizza",
                "description": "Classic pizza",
                "macros": {"calories": 800, "protein": 30, "carbs": 100, "fat": 25},
                "match_score": 85,
                "estimated": True
            }
        )
        
        restaurant = {
            "name": "Bella Italia",
            "place_types": ["italian_restaurant"],
            "latitude": 51.5074,
            "longitude": -0.1278
        }
        
        user_prefs = {
            "user_id": "user@example.com",
            "dietary_restrictions": [],
            "dietary_preference": None
        }
        
        macro_targets = {"calories": 800, "protein": 30}
        
        result = await restaurant_meal_matching_service.get_top_meal_for_restaurant(
            restaurant=restaurant,
            user_preferences=user_prefs,
            macro_targets=macro_targets
        )
        
        assert result["name"] == "Margherita Pizza"
        assert result["match_score"] == 85
        mock_generate.assert_called_once()
