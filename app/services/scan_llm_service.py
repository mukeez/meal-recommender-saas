"""AI service for analyzing food images.

This module provides the ScanLLMService for interacting with vision models
to analyze food images and extract nutritional information.
"""
import logging
import json
import base64

from app.core.config import settings
from app.services.base_llm_service import BaseLLMService, LLMServiceError

logger = logging.getLogger(__name__)

class ScanLLMService(BaseLLMService):
    """AI service for analyzing food images."""

    def __init__(self):
        super().__init__()

    def _build_prompt(self, request: str = None) -> str:
        """
        Construct the prompt string. In this case, the prompt is passed directly.
        """
        return """Identify this image as a complete meal or dish. Do not break it down into individual components.

Provide a single, descriptive name for the entire meal as it appears in the image. If there are multiple components, describe them as one unified dish (e.g., "Jollof rice with grilled chicken and plantains" rather than separate items).

For the complete meal shown, provide:
1. Descriptive name of the entire meal/dish (be as descriptive as possible)
2. Estimated total weight of the entire serving shown (as a numeric value in grams)
3. Serving unit (Always use "grams")  
4. Total estimated calories for the entire serving shown
5. Total estimated protein for the entire serving shown
6. Total estimated carbs for the entire serving shown
7. Total estimated fat for the entire serving shown
8. List of ALL individual ingredients that make up this meal (as an array of strings)

IMPORTANT: 
- Treat this as ONE complete meal with total nutritional values
- Detect individual ingredients that compose the meal

Format your response as a valid JSON object with this structure:
{{
  "items": [
    {{
      "name": "Complete descriptive meal name",
      "amount": number,
      "serving_unit": "grams", 
      "calories": number,
      "protein": number,
      "carbs": number,
      "fat": number
    }}
  ],
  "detected_ingredients": ["ingredient1", "ingredient2", "ingredient3"]
}}
"""

    def _parse_response(self, content: str) -> dict:
        """
        Parse raw AI output into structured objects.
        """
        return json.loads(content)

    async def analyze_image(self, encoded_image: str) -> dict:
        """
        Analyze a food image using a vision model.

        Args:
            encoded_image: Base64 encoded image string.

        Returns:
            The JSON response from the AI service.
        """
        logger.info(f"Using vision model: {self.model}")

        try:
            logger.info("Sending request to Vision API via litellm...")
            
            result = await self.generate_response(
                system_prompt="You are a food analysis assistant.",
                request=None, # Prompt is now built-in
                encoded_image=encoded_image,
                max_tokens=1000,
            )
            
            logger.info("Successfully received response from Vision API")
            return result

        except (LLMServiceError, json.JSONDecodeError) as e:
            logger.error(f"Error in image analysis: {str(e)}")
            raise LLMServiceError(f"Vision analysis failed: {e}")
        
        except Exception as e:
            logger.error(f"An unexpected error occurred during image analysis: {e}")
            raise LLMServiceError(f"An unexpected error occurred: {e}")

scan_llm_service = ScanLLMService()
