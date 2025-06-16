import pytest
from unittest.mock import AsyncMock
from app.tests.constants.macros import MOCK_MACRO_DATA
from app.tests.constants.location import MOCK_LOCATION_DATA


@pytest.fixture(scope="function")
def mock_meal_llm_suggest_meals(mocker):
    """Fixture to patch and provide a mock for meal_llm_service.get_meal_suggestions."""
    mock = mocker.patch(
        "app.api.endpoints.meals.meal_llm_service.get_meal_suggestions",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_restaurant_find_nearby(mocker):
    """Fixture to patch and provide a mock for restaurant_service.find_restaurants_for_location."""
    mock = mocker.patch(
        "app.api.endpoints.meals.restaurant_service.find_restaurants_for_location",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_meal_log(mocker):
    """Fixture to patch and provide a mock for meal_service.log_meal."""
    mock = mocker.patch(
        "app.api.endpoints.meals.meal_service.log_meal",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_meal_get_today(mocker):
    """Fixture to patch and provide a mock for meal_service.get_meals_for_today."""
    mock = mocker.patch(
        "app.api.endpoints.meals.meal_service.get_meals_for_today",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_meal_get_progress(mocker):
    """Fixture to patch and provide a mock for meal_service.get_daily_progress."""
    mock = mocker.patch(
        "app.api.endpoints.meals.meal_service.get_daily_progress",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_meal_get_progress_summary(mocker):
    """Fixture to patch and provide a mock for meal_service.get_progress_summary."""
    mock = mocker.patch(
        "app.api.endpoints.meals.meal_service.get_progress_summary",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_meal_get_first_date(mocker):
    """Fixture to patch and provide a mock for meal_service.get_first_meal_date."""
    mock = mocker.patch(
        "app.api.endpoints.meals.meal_service.get_first_meal_date",
        new_callable=AsyncMock,
    )
    return mock


@pytest.fixture(scope="function")
def mock_meal_suggestion_response():
    """Fixture providing a mock MealSuggestionResponse model instance."""
    from app.models.meal import MealSuggestionResponse, MealSuggestion, MacroNutrients, Restaurant

    return MealSuggestionResponse(
        meals=[
            MealSuggestion(
                name="Grilled Chicken Salad",
                description="Fresh salad with grilled chicken breast",
                macros=MacroNutrients(
                    calories=450,
                    protein=35,
                    carbs=30,
                    fat=15
                ),
                restaurant=Restaurant(
                    name="Healthy Bites",
                    location="123 Main St"
                )
            )
        ]
    )


@pytest.fixture(scope="function")
def mock_logged_meal():
    """Fixture providing a mock LoggedMeal model instance."""
    from app.models.meal import LoggedMeal

    return LoggedMeal(
        id="123e4567-e89b-12d3-a456-426614174000",
        user_id="user-123",
        name="Lunch",
        description="Chicken and rice",
        calories=500,
        protein=35,
        carbs=50,
        fat=15,
        timestamp="2025-05-31T12:00:00Z"
    )