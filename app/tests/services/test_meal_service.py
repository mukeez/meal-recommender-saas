import pytest
from datetime import time
from app.models.meal import MealType
from app.services.meal_service import meal_service

class TestMealClassification:
    
    @pytest.mark.parametrize(
        "test_time,expected_type", 
        [
            (time(4, 0), MealType.BREAKFAST),
            (time(7, 30), MealType.BREAKFAST),
            (time(10, 59), MealType.BREAKFAST),
            (time(11, 0), MealType.LUNCH),
            (time(13, 45), MealType.LUNCH),
            (time(15, 59), MealType.LUNCH),
            (time(16, 0), MealType.DINNER),
            (time(19, 0), MealType.DINNER),
            (time(22, 0), MealType.DINNER),
            (time(22, 1), MealType.OTHER),
            (time(2, 30), MealType.OTHER),
            (time(3, 59), MealType.OTHER),
        ]
    )
    def test_meal_classification(self, test_time, expected_type):
        """Test meal classification based on time of day."""
        assert meal_service._classify_meal_by_time(test_time) == expected_type