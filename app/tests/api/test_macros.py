import pytest
from app.core.config import settings
from app.models.macro_tracking import ActivityLevel, GoalType, Sex
from app.models.user import HeightUnitPreference, WeightUnitPreference
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
            "height_unit_preference": MacrosTestConstants.HEIGHT_UNIT_PREFERENCE.value,
            "weight_unit_preference": MacrosTestConstants.WEIGHT_UNIT_PREFERENCE.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/macros-setup", json=macros_data
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
            "height_unit_preference": MacrosTestConstants.HEIGHT_UNIT_PREFERENCE.value,
            "weight_unit_preference": MacrosTestConstants.WEIGHT_UNIT_PREFERENCE.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/macros-setup", json=macros_data
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
            "height_unit_preference": HeightUnitPreference.IMPERIAL.value,
            "weight_unit_preference": WeightUnitPreference.IMPERIAL.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/macros-setup", json=macros_data
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
            "height_unit_preference": MacrosTestConstants.HEIGHT_UNIT_PREFERENCE.value,
            "weight_unit_preference": MacrosTestConstants.WEIGHT_UNIT_PREFERENCE.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/macros-setup", json=macros_data
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
            "height_unit_preference": MacrosTestConstants.HEIGHT_UNIT_PREFERENCE.value,
            "weight_unit_preference": MacrosTestConstants.WEIGHT_UNIT_PREFERENCE.value,
        }
        
        # Update with invalid value
        macros_data.update(invalid_data)

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/macros-setup", json=macros_data
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
        calculated_calories = (data["protein"] * 4) + (data["carbs"] * 4) + (data["fat"] * 9)
        assert abs(calculated_calories - data["calories"]) < 5  # Allow small rounding differences
        
    async def test_adjust_distribution_protein_only(self, authenticated_client, mock_save_user_preferences):
        """Test adjustment with only protein specified."""

        request_data = {
            "protein": 120,
            "carbs": None,
            "fat": None,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/adjust-macros", 
            json=request_data
        )

        assert response.status_code == 200
        
        data = response.json()
        assert data["protein"] == 120
        assert data["carbs"] > 0
        assert data["fat"] > 0

    async def test_adjust_distribution_all_macros(self, authenticated_client, mock_save_user_preferences):
        """Test adjustment with all macros specified (should calculate calories)."""

        request_data = {
            "protein": 100,
            "carbs": 200,
            "fat": 50,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/adjust-macros", 
            json=request_data
        )

        assert response.status_code == 200
        
        data = response.json()
        assert data["protein"] == 100
        assert data["carbs"] == 200
        assert data["fat"] == 50
        
        # Calculate expected calories: (100*4) + (200*4) + (50*9) = 1650
        expected_calories = (100 * 4) + (200 * 4) + (50 * 9)
        assert data["calories"] == expected_calories

    async def test_adjust_distribution_no_macros(self, authenticated_client):
        """Test adjustment with no macros specified (should fail)."""

        request_data = {
            "protein": None,
            "carbs": None,
            "fat": None,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/adjust-macros", 
            json=request_data
        )

        # Should return an error since no macros are specified
        assert response.status_code == 400


@pytest.mark.asyncio
class TestCalculateMacrosEndpoint:
    """Test cases for the new calculate-macros endpoint for meal calculations."""

    async def test_calculate_macros_success(self, authenticated_client):
        """Test successful macro calculation with amount change."""
        
        request_data = {
            "base_calories": 300.0,
            "base_protein": 25.0,
            "base_carbs": 30.0,
            "base_fat": 10.0,
            "base_amount": 1.0,
            "new_amount": 2.0
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/calculate-macros", 
            json=request_data
        )

        assert response.status_code == 200
        
        data = response.json()
        
        # Verify that macros are doubled (2x multiplier)
        assert data["calories"] == 600.0
        assert data["protein"] == 50.0
        assert data["carbs"] == 60.0
        assert data["fat"] == 20.0

    async def test_calculate_macros_fractional_amount(self, authenticated_client):
        """Test macro calculation with fractional amount."""
        
        request_data = {
            "base_calories": 400.0,
            "base_protein": 30.0,
            "base_carbs": 40.0,
            "base_fat": 15.0,
            "base_amount": 2.0,
            "new_amount": 1.5
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/calculate-macros", 
            json=request_data
        )

        assert response.status_code == 200
        
        data = response.json()
        
        # Verify that macros are calculated with 0.75 multiplier (1.5/2.0)
        assert data["calories"] == 300.0  # 400 * 0.75
        assert data["protein"] == 22.5   # 30 * 0.75
        assert data["carbs"] == 30.0     # 40 * 0.75
        assert data["fat"] == 11.25      # 15 * 0.75

    async def test_calculate_macros_zero_new_amount(self, authenticated_client):
        """Test validation error when new amount is zero."""
        
        request_data = {
            "base_calories": 300.0,
            "base_protein": 25.0,
            "base_carbs": 30.0,
            "base_fat": 10.0,
            "base_amount": 1.0,
            "new_amount": 0.0
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/calculate-macros", 
            json=request_data
        )

        assert response.status_code == 400
        data = response.json()
        assert "New amount must be greater than 0" in data["detail"]


