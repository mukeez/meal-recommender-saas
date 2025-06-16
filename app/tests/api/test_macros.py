import pytest
from app.core.config import settings
from app.models.macro_tracking import ActivityLevel, GoalType, UnitPreference, Sex
from app.tests.constants.macros import MacrosTestConstants


@pytest.mark.asyncio
class TestMacrosEndpoint:
    
    async def test_calculate_macros_success(self, authenticated_client, mock_save_user_preferences, mock_macros_update_user_profile):
        """Integration test for successful calculation of user macros."""

        macros_data = {
            "age": MacrosTestConstants.AGE.value,
            "weight": MacrosTestConstants.WEIGHT.value,
            "height": MacrosTestConstants.HEIGHT.value,
            "sex": MacrosTestConstants.SEX.value,
            "activity_level": MacrosTestConstants.ACTIVITY_LEVEL.value,
            "goal_type": GoalType.MAINTAIN.value,
            "progress_rate": MacrosTestConstants.PROGRESS_RATE.value,
            "unit_preference": MacrosTestConstants.UNIT_PREFERENCE.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/calculate-macros", json=macros_data
        )
        assert response.status_code == 200
        
        # Verify save_user_preferences was called
        mock_save_user_preferences.assert_called_once()

        mock_macros_update_user_profile.assert_called_once()

        expected_keys = ["calories", "protein", "carbs", "fat", 
                         "progress_rate", "deficit_surplus", "is_safe"]

        data = response.json()
        
        for key in expected_keys:
            assert key in data
    
    
    
    
    async def test_calculate_macros_with_target_weight(self, authenticated_client, mock_save_user_preferences, mock_macros_update_user_profile):
        """Test calculation of macros with a target weight goal."""

        macros_data = {
            "age": MacrosTestConstants.AGE.value,
            "weight": MacrosTestConstants.WEIGHT.value,
            "height": MacrosTestConstants.HEIGHT.value,
            "sex": MacrosTestConstants.SEX.value,
            "activity_level": MacrosTestConstants.ACTIVITY_LEVEL.value,
            "goal_type": GoalType.LOSE.value,
            "progress_rate": 1.0,  # 1 kg per week weight loss
            "target_weight": MacrosTestConstants.WEIGHT.value - 10,  # 10kg less
            "unit_preference": MacrosTestConstants.UNIT_PREFERENCE.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/calculate-macros", json=macros_data
        )


        assert response.status_code == 200
        
        # Verify save_user_preferences was called
        mock_save_user_preferences.assert_called_once()

        mock_macros_update_user_profile.assert_called_once()
        
        data = response.json()
        
        # Verify time_to_goal is present and makes sense
        assert "time_to_goal" in data
        assert data["time_to_goal"] is not None
        assert "weeks" in data["time_to_goal"]
        assert "days" in data["time_to_goal"]
        assert "estimated_date" in data["time_to_goal"]
        assert "is_possible" in data["time_to_goal"]
        
        # Check that the calculation makes sense: 10 lbs at 1 lb/week = ~10 weeks
        assert data["time_to_goal"]["weeks"] >= 9.5  # Allow for rounding
        assert data["time_to_goal"]["weeks"] <= 10.5
        assert data["time_to_goal"]["is_possible"] is True
    
    async def test_calculate_macros_imperial_units(self, authenticated_client, mock_save_user_preferences, mock_macros_update_user_profile):
        """Test calculation with imperial units."""

        macros_data = {
            "age": MacrosTestConstants.AGE.value,
            "weight": 180,  # lbs
            "height": 70,   # inches
            "sex": MacrosTestConstants.SEX.value,
            "activity_level": MacrosTestConstants.ACTIVITY_LEVEL.value,
            "goal_type": MacrosTestConstants.GOAL_TYPE.value,
            "progress_rate": MacrosTestConstants.PROGRESS_RATE.value,
            "unit_preference": UnitPreference.IMPERIAL.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/calculate-macros", json=macros_data
        )
        assert response.status_code == 200
        
        # Verify save_user_preferences was called
        mock_save_user_preferences.assert_called_once()

        mock_macros_update_user_profile.assert_called_once()
        
        data = response.json()
        assert data["calories"] > 0
    
    async def test_unsafe_deficit(self, authenticated_client, mock_save_user_preferences, mock_macros_update_user_profile):
        """Test that an unsafe deficit is properly flagged."""

        macros_data = {
            "age": MacrosTestConstants.AGE.value,
            "weight": MacrosTestConstants.WEIGHT.value,
            "height": MacrosTestConstants.HEIGHT.value,
            "sex": MacrosTestConstants.SEX.value,
            "activity_level": ActivityLevel.SEDENTARY.value,  # Lower TDEE
            "goal_type": GoalType.LOSE.value,
            "progress_rate": 3.0,  # Very aggressive weight loss
            "unit_preference": MacrosTestConstants.UNIT_PREFERENCE.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/calculate-macros", json=macros_data
        )

        assert response.status_code == 200
        
        # Verify save_user_preferences was called
        mock_save_user_preferences.assert_called_once()

        mock_macros_update_user_profile.assert_called_once()
        
        data = response.json()
        
        # Verify the request is marked as unsafe
        assert data["is_safe"] is False
    
    @pytest.mark.parametrize("invalid_data", [
        {"age": 15},  # Too young
        {"age": 110},  # Too old
        {"weight": -5},  # Negative weight
        {"height": 0},  # Zero height
    ])
    async def test_invalid_inputs(self, authenticated_client, invalid_data, mock_macros_update_user_profile):
        """Test validation of invalid inputs."""

        macros_data = {
            "age": MacrosTestConstants.AGE.value,
            "weight": MacrosTestConstants.WEIGHT.value,
            "height": MacrosTestConstants.HEIGHT.value,
            "sex": MacrosTestConstants.SEX.value,
            "activity_level": MacrosTestConstants.ACTIVITY_LEVEL.value,
            "goal_type": MacrosTestConstants.GOAL_TYPE.value,
            "progress_rate": MacrosTestConstants.PROGRESS_RATE.value,
            "unit_preference": MacrosTestConstants.UNIT_PREFERENCE.value,
        }
        
        # Update with invalid value
        macros_data.update(invalid_data)

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/calculate-macros", json=macros_data
        )

        # Should return validation error
        assert response.status_code == 422

    async def test_adjust_distribution_success(self, authenticated_client, mock_save_user_preferences):
        """Test successful adjustment of macro distribution."""

        request_data = {
            "protein": 150,
            "carbs": None,
            "fat": 60,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/adjust-macros", 
            json=request_data
        )

        assert response.status_code == 200
        
        # Verify save_user_preferences was called
        mock_save_user_preferences.assert_called_once()
        
        data = response.json()
        
        assert data["calories"] == 1340
        assert data["protein"] == 150
        assert data["fat"] == 60
        assert data["carbs"] > 0
        
        # Verify that the energy equation balances
        # (4 * protein) + (4 * carbs) + (9 * fat) should be close to total calories
        calculated_calories = (4 * data["protein"]) + (4 * data["carbs"]) + (9 * data["fat"])
        assert abs(calculated_calories - data["calories"]) <= 10  # Allow small rounding differences
    
    async def test_adjust_distribution_all_macros(self, authenticated_client, mock_save_user_preferences):
        """Test adjustment with all macros specified."""

        request_data = {
            "calories": 2000,
            "protein": 150,
            "carbs": 150,
            "fat": 60,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/adjust-macros", 
            json=request_data
        )

        print(f"here is the response:{response.json()}")
        assert response.status_code == 200
        
        # Verify save_user_preferences was called
        mock_save_user_preferences.assert_called_once()
        
        
    
    async def test_adjust_distribution_no_macros(self, authenticated_client):
        """Test adjustment with no macros specified (should use default ratio)."""

        request_data = {
            "calories": 2000,
            "protein": None,
            "carbs": None,
            "fat": None,
        }

        # This should return a validation error since at least one macro is required
        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/adjust-macros", 
            json=request_data
        )

        assert response.status_code == 422


