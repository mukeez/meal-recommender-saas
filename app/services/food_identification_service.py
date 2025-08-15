"""Food identification service for neutral food analysis.

This service provides unbiased food identification without indigenous classification bias.
Used as Stage 2 in the 3-stage indigenous dish detection pipeline.
"""

import logging
import json
from typing import Dict, Any
from app.services.base_llm_service import BaseLLMService, LLMServiceError

logger = logging.getLogger(__name__)


class FoodIdentificationService(BaseLLMService):
    """Service for neutral food identification without indigenous bias."""

    def __init__(self):
        super().__init__()
        self.model = "gpt-4o-mini"

    def _build_prompt(self, request: Any) -> str:
        """
        Construct the prompt string.
        """
        return """Analyze this food image and provide neutral food identification.

Focus on:
1. What food items you can see
2. Main ingredients visible
3. Cooking methods apparent
4. Presentation style
5. Basic food categorization (e.g., rice dish, stew, grilled meat, etc.)

Do NOT make assumptions about cultural origin or traditional significance.
Just describe what you observe objectively.

Provide your analysis in the following JSON format:
{
    "identified_food": "Name of the main dish/food",
    "food_category": "Basic category (e.g., rice dish, meat stew, vegetable curry, etc.)",
    "visible_ingredients": ["ingredient1", "ingredient2", "ingredient3"],
    "cooking_methods": ["method1", "method2"],
    "presentation_style": "Description of how food is presented",
    "confidence": 0.85,
    "observations": "Additional objective observations about the food"
}"""

    def _parse_response(self, content: str) -> Any:
        """
        Parse raw AI output into structured objects.
        """
        return json.loads(content)

    async def identify_food(self, encoded_image: str, user_id: str = None) -> Dict[str, Any]:
        """
        Identify food in image without indigenous classification bias.
        
        Args:
            encoded_image: Base64 encoded image string
            user_id: Optional user ID for tracking and rate limiting.
            
        Returns:
            Dictionary containing food identification results
        """
        try:
            logger.info("Performing neutral food identification...")
            
            result = await self.generate_response(
                system_prompt="You are a neutral food identification assistant.",
                request=None, # Prompt is fixed, so request is not used here
                encoded_image=encoded_image,
                max_tokens=800,
                temperature=0.3,
                user_id=user_id,
            )
            
            logger.info(f"Food identification completed: {result.get('identified_food', 'Unknown')}")
            return result

        except (LLMServiceError, json.JSONDecodeError) as e:
            logger.error(f"Error in food identification: {str(e)}")
            # Return fallback result
            return {
                "identified_food": "Unknown Food",
                "food_category": "Unidentified",
                "visible_ingredients": [],
                "cooking_methods": [],
                "presentation_style": "Unable to analyze",
                "confidence": 0.0,
                "observations": f"Analysis failed: {str(e)}"
            }


# Create service instance
food_identification_service = FoodIdentificationService()