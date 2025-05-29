import pytest
from app.core.config import settings
from app.tests.constants.macros import MacrosTestConstants


@pytest.mark.asyncio
class TestMacrosEndpoint:
    async def test_caculate_macros_success(self, authenticated_client):
        """Integration test for successful calculation of user macros."""

        macros_data = {
            "age": MacrosTestConstants.AGE.value,
            "weight": MacrosTestConstants.WEIGHT.value,
            "height": MacrosTestConstants.HEIGHT.value,
            "sex": MacrosTestConstants.SEX.value,
            "activity_level": MacrosTestConstants.ACTIVITY_LEVEL.value,
            "goal": MacrosTestConstants.GOAL.value,
            "unit_system": MacrosTestConstants.UNIT_SYSTEM.value,
        }

        response = authenticated_client.post(
            f"{settings.API_V1_STR}/macros/calculate-macros", json=macros_data
        )

        assert response.status_code == 200

        expected_keys = ["calories", "protein", "carbs", "fat"]

        for key in response.json().keys():
            assert key in expected_keys
