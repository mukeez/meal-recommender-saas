"""Food identification service for neutral food analysis.

This service provides unbiased food identification without indigenous classification bias.
Used as Stage 2 in the 3-stage indigenous dish detection pipeline.
"""

import logging
import json
from typing import Dict, Any, List
from app.services.base_llm_service import BaseLLMService, LLMServiceError

logger = logging.getLogger(__name__)


class FoodIdentificationService(BaseLLMService):
    """Service for neutral food identification without indigenous bias."""

    async def identify_food(self, encoded_image: str) -> Dict[str, Any]:
        """
        Identify food in image without indigenous classification bias.
        
        Args:
            encoded_image: Base64 encoded image string
            
        Returns:
            Dictionary containing food identification results
        """
        prompt = """Analyze this food image and provide neutral food identification.

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

        try:
            logger.info("Performing neutral food identification...")
            
            # Use the same vision model as scan service
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded_image}"
                                },
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=800,
                temperature=0.3,
            )
            
            ai_response = response.choices[0].message.content
            result = json.loads(ai_response)
            
            logger.info(f"Food identification completed: {result.get('identified_food', 'Unknown')}")
            return result

        except Exception as e:
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