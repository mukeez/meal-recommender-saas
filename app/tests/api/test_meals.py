import pytest
from fastapi import HTTPException, status
from app.core.config import settings
from app.tests.constants.user import UserTestConstants
from app.tests.constants.location import MOCK_LOCATION_DATA
from app.tests.constants.macros import MOCK_MACRO_DATA
from app.tests.constants.meals import MOCK_RESTAURANT_DATA
import httpx
from unittest.mock import patch
from datetime import date


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
            "meal_time": "2025-05-31T12:00:00Z",
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
                "meal_time": "2025-05-31T08:00:00Z",
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
                "meal_time": "2025-05-31T12:00:00Z",
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

    async def test_get_progress_summary_success(
        self, authenticated_client, mock_meal_get_progress_summary
    ):
        """Integration test for successful progress summary retrieval."""

        # Mock progress summary response
        expected_values = {
            "daily_macros": [
                {
                    "date": "2025-06-01",
                    "calories": 1800,
                    "protein": 120,
                    "carbs": 180,
                    "fat": 60
                },
                {
                    "date": "2025-06-02",
                    "calories": 2100,
                    "protein": 140,
                    "carbs": 200,
                    "fat": 70
                }
            ],
            "average_macros": {
                "calories": 1950.0,
                "protein": 130.0,
                "carbs": 190.0,
                "fat": 65.0
            },
            "target_macros": {
                "calories": 2000,
                "protein": 150,
                "carbs": 200,
                "fat": 70
            },
            "comparison_percentage": {
                "calories": 97.5,
                "protein": 86.7,
                "carbs": 95.0,
                "fat": 92.9
            },
            "start_date": "2025-06-01",
            "end_date": "2025-06-02",
            "days_with_logs": 2,
            "total_days": 2
        }

        mock_meal_get_progress_summary.return_value = expected_values

        # Test with explicit start_date and end_date
        response = authenticated_client.get(
            f"{settings.API_V1_STR}/meals/progress?start_date=2025-06-01&end_date=2025-06-02"
        )

        assert response.status_code == 200
        assert response.json() == expected_values
        
        # Verify the mock was called with correct parameters
        mock_meal_get_progress_summary.assert_called_with(
            UserTestConstants.MOCK_USER_ID.value, 
            pytest.approx(date(2025, 6, 1)), 
            pytest.approx(date(2025, 6, 2))
        )
        
        # Reset the mock for the next call
        mock_meal_get_progress_summary.reset_mock()
        mock_meal_get_progress_summary.return_value = expected_values
        
        # Test with period parameter
        response = authenticated_client.get(
            f"{settings.API_V1_STR}/meals/progress?period=1W"
        )
        
        assert response.status_code == 200
        assert response.json() == expected_values
        
        assert mock_meal_get_progress_summary.called
        
        # Testing default parameters (no query params)
        mock_meal_get_progress_summary.reset_mock()
        mock_meal_get_progress_summary.return_value = expected_values
        
        response = authenticated_client.get(
            f"{settings.API_V1_STR}/meals/progress"
        )
        
        assert response.status_code == 200
        assert response.json() == expected_values
        assert mock_meal_get_progress_summary.called

   
    async def test_get_progress_summary_failed(
        self, authenticated_client, mock_meal_get_progress_summary
    ):
        """Integration test for failed progress summary retrieval."""

        mock_meal_get_progress_summary.side_effect = Exception("Database error")

        response = authenticated_client.get(
            f"{settings.API_V1_STR}/meals/progress?period=1M"
        )

        assert response.status_code == 500
        assert "Error retrieving progress data" in response.json()["detail"]
        assert mock_meal_get_progress_summary.called

    async def test_get_progress_summary_empty_state(
        self, authenticated_client, mock_meal_get_progress_summary, mock_meal_get_first_date
    ):
        """Test progress summary with no meal data."""
        
        # Set up mocks to simulate empty state
        mock_meal_get_first_date.return_value = None
        
        # Create empty response data
        empty_response = {
            "daily_macros": [],  # This would actually contain date entries with zero values
            "average_macros": {
                "calories": 0,
                "protein": 0,
                "carbs": 0,
                "fat": 0
            },
            "target_macros": {
                "calories": 2000,
                "protein": 150,
                "carbs": 200,
                "fat": 70
            },
            "comparison_percentage": {
                "calories": 0,
                "protein": 0,
                "carbs": 0,
                "fat": 0
            },
            "start_date": "2025-06-01",
            "end_date": "2025-06-07",
            "days_with_logs": 0,
            "total_days": 7
        }
        
        mock_meal_get_progress_summary.return_value = empty_response
        
        response = authenticated_client.get(
            f"{settings.API_V1_STR}/meals/progress?start_date=2025-06-01&end_date=2025-06-07"
        )
        
        assert response.status_code == 200
        assert response.json()["days_with_logs"] == 0
        assert response.json()["average_macros"]["calories"] == 0
        assert response.json()["comparison_percentage"]["protein"] == 0