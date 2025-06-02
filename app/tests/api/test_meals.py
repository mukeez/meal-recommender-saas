import pytest
from fastapi import HTTPException, status
from app.core.config import settings
from app.tests.constants.location import MOCK_LOCATION_DATA
from app.tests.constants.macros import MOCK_MACRO_DATA
from app.tests.constants.meals import MOCK_RESTAURANT_DATA
import httpx
from unittest.mock import patch


@pytest.mark.asyncio
class TestMealsEndpoint:
    async def test_suggest_meals_success(
        self, authenticated_client, mock_meal_llm_suggest_meals, mock_restaurant_find_nearby
    ):
        """Integration test for successful meal suggestion generation."""

        mock_restaurant_find_nearby.return_value = MOCK_RESTAURANT_DATA

        expected_values = {
            "meals": [
                {
                    "name": "Grilled Chicken Salad",
                    "description": "Fresh salad with grilled chicken breast",
                    "macros": {
                        "calories": 450,
                        "protein": 35,
                        "carbs": 30,
                        "fat": 15
                    },
                    "restaurant": {
                        "name": "Healthy Bites",
                        "location": "123 Main St"
                    }
                }
            ]
        }

        mock_meal_llm_suggest_meals.return_value = expected_values

        request_data = {
            "location": MOCK_LOCATION_DATA["display_name"],
            "latitude": MOCK_LOCATION_DATA["latitude"],
            "longitude": MOCK_LOCATION_DATA["longitude"],
            "calories": MOCK_MACRO_DATA["calories"],
            "protein": MOCK_MACRO_DATA["protein"],
            "carbs": MOCK_MACRO_DATA["carbs"],
            "fat": MOCK_MACRO_DATA["fat"]
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/meals/suggest-meals", 
            json=request_data
        )

        assert response.status_code == 200
        assert response.json() == expected_values
        mock_restaurant_find_nearby.assert_called_once_with(
            location=request_data["location"],
            latitude=request_data["latitude"],
            longitude=request_data["longitude"]
        )
        mock_meal_llm_suggest_meals.assert_called_once()

    async def test_suggest_meals_failed(
        self, authenticated_client, mock_meal_llm_suggest_meals, mock_restaurant_find_nearby
    ):
        """Integration test for failed meal suggestion."""

        mock_restaurant_find_nearby.return_value = MOCK_RESTAURANT_DATA

        mock_meal_llm_suggest_meals.side_effect = Exception("Service error")

        request_data = {
            "location": MOCK_LOCATION_DATA["display_name"],
            "latitude": MOCK_LOCATION_DATA["latitude"],
            "longitude": MOCK_LOCATION_DATA["longitude"],
            "calories": MOCK_MACRO_DATA["calories"],
            "protein": MOCK_MACRO_DATA["protein"],
            "carbs": MOCK_MACRO_DATA["carbs"],
            "fat": MOCK_MACRO_DATA["fat"]
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/meals/suggest-meals", 
            json=request_data
        )

        assert response.status_code == 500
        assert response.json() == {"detail": "Error generating meal suggestions"}
        mock_restaurant_find_nearby.assert_called_once_with(   
            location=request_data["location"],
            latitude=request_data["latitude"],
            longitude=request_data["longitude"]
        )
        mock_meal_llm_suggest_meals.assert_called_once()

    async def test_log_meal_success(
        self, authenticated_client, mock_meal_log
    ):
        """Integration test for successful meal logging."""

        expected_values = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "user_id": "user-123",
            "name": "Lunch",
            "description": "Chicken and rice",
            "calories": 500,
            "protein": 35,
            "carbs": 50,
            "fat": 15,
            "timestamp": "2025-05-31T12:00:00Z",
            "meal_type": "lunch"
        }

        mock_meal_log.return_value = expected_values

        request_data = {
            "name": "Lunch",
            "description": "Chicken and rice",
            "calories": 500,
            "protein": 35,
            "carbs": 50,
            "fat": 15
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/meals/add", 
            json=request_data
        )

        assert response.status_code == 201
        assert response.json() == expected_values
        mock_meal_log.assert_called_once()

    async def test_log_meal_failed(
        self, authenticated_client, mock_meal_log
    ):
        """Integration test for failed meal logging."""

        mock_meal_log.side_effect = Exception("Database error")

        request_data = {
            "name": "Lunch",
            "description": "Chicken and rice",
            "calories": 500,
            "protein": 35,
            "carbs": 50,
            "fat": 15
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/meals/add", 
            json=request_data
        )

        assert response.status_code == 500
        assert "Error logging meal" in response.json()["detail"]
        mock_meal_log.assert_called_once()

    async def test_get_today_meals_success(
        self, authenticated_client, mock_meal_get_today
    ):
        """Integration test for successfully retrieving today's meals."""

        expected_values = [
            {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "user-123",
                "name": "Breakfast",
                "description": "Oatmeal with fruit",
                "calories": 300,
                "protein": 15,
                "carbs": 50,
                "fat": 5,
                "timestamp": "2025-05-31T08:00:00Z",
                "meal_type": "breakfast"
            },
            {
                "id": "223e4567-e89b-12d3-a456-426614174001",
                "user_id": "user-123",
                "name": "Lunch",
                "description": "Chicken and rice",
                "calories": 500,
                "protein": 35,
                "carbs": 50,
                "fat": 15,
                "timestamp": "2025-05-31T12:00:00Z",
                "meal_type": "lunch"
            }
        ]

        mock_meal_get_today.return_value = expected_values

        response = authenticated_client.get(
            f"{settings.API_V1_STR}/meals/today"
        )

        assert response.status_code == 200
        assert response.json() == expected_values
        mock_meal_get_today.assert_called_once()

    async def test_get_today_meals_failed(
        self, authenticated_client, mock_meal_get_today
    ):
        """Integration test for failed retrieval of today's meals."""

        mock_meal_get_today.side_effect = Exception("Database error")

        response = authenticated_client.get(
            f"{settings.API_V1_STR}/meals/today"
        )

        assert response.status_code == 500
        assert "Error retrieving today's meals" in response.json()["detail"]
        mock_meal_get_today.assert_called_once()

    async def test_get_daily_progress_success(
        self, authenticated_client, mock_meal_get_progress
    ):
        """Integration test for successful daily progress retrieval."""

        expected_values = {
            "logged_macros": {
                "calories": 800,
                "protein": 50,
                "carbs": 100,
                "fat": 20
            },
            "target_macros": {
                "calories": 2000,
                "protein": 150,
                "carbs": 250,
                "fat": 70
            },
            "progress_percentage": {
                "calories": 40.0,
                "protein": 33.33,
                "carbs": 40.0,
                "fat": 28.57
            }
        }

        mock_meal_get_progress.return_value = expected_values

        response = authenticated_client.get(
            f"{settings.API_V1_STR}/meals/progress/today"
        )

        assert response.status_code == 200
        assert response.json() == expected_values
        mock_meal_get_progress.assert_called_once()

    async def test_get_daily_progress_failed(
        self, authenticated_client, mock_meal_get_progress
    ):
        """Integration test for failed daily progress retrieval."""

        mock_meal_get_progress.side_effect = Exception("Calculation error")

        response = authenticated_client.get(
            f"{settings.API_V1_STR}/meals/progress/today"
        )

        assert response.status_code == 500
        assert "Error calculating daily progress" in response.json()["detail"]
        mock_meal_get_progress.assert_called_once()