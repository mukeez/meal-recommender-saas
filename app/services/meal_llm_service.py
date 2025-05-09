"""AI service for generating meal suggestions.

This module provides functions to interact with the OpenAI API
to generate meal suggestions based on user requirements.
"""

import json
from typing import Dict, Any, List
import openai
from openai import OpenAI

from app.core.config import settings
from app.models.meal import MealSuggestion, MealSuggestionRequest
from app.services.base_llm_service import BaseLLMService, LLMServiceError


class MealLLMService(BaseLLMService):
    """Service for interacting with OpenAI API."""

    def __init__(self):
        """Initialize the OpenAI client."""
        super().__init__()

    async def get_meal_suggestions(
        self, request: MealSuggestionRequest
    ) -> List[MealSuggestion]:
        """Get meal suggestions from OpenAI API.

        Args:
            request: The meal suggestion request containing user preferences

        Returns:
            List of meal suggestions that match the user's criteria

        Raises:
            LLMServiceError: If there is an error communicating with the API
                            or processing the response
        """
        try:
            system_prompt = "You are a nutrition expert and restaurant knowledge specialist. Provide accurate, concise meal suggestions based on the user's macro requirements."
            suggestions = await self.generate_response(
                system_prompt=system_prompt, request=request
            )
            return suggestions
        except openai.OpenAIError as e:
            raise LLMServiceError(f"OpenAI API error: {str(e)}")
        except json.JSONDecodeError:
            raise LLMServiceError("Failed to parse AI response as JSON")
        except Exception as e:
            raise LLMServiceError(f"Unexpected error: {str(e)}")

    def _build_prompt(self, request: MealSuggestionRequest) -> str:
        """Build a prompt for the OpenAI API.

        Args:
            request: The meal suggestion request

        Returns:
            Formatted prompt string
        """
        return f"""Suggest 5-8 meal options from restaurants in {request.location} that can help me meet these macro requirements:
- Calories: {request.calories} kcal
- Protein: {request.protein} g
- Carbs: {request.carbs} g
- Fat: {request.fat} g

For each meal suggestion, provide:
1. Meal name
2. Brief description
3. Estimated macros (calories, protein, carbs, fat) — note these can be approximate
4. Restaurant name and location

Format your response as a JSON object with a "meals" property containing an array of meal objects. Each meal object should include:
- name (string)
- description (string)
- macros (object) with numeric values for "calories", "protein", "carbs", "fat"
- restaurant (object) with "name" and "location" properties

Only suggest restaurants that exist in {request.location}.

Example format (do not use these values, please suggest real meals and check if these name and location exist near {request.location} else do not return in json):
```json
{{
  "meals": [
    {{
      "name": "Lorem Ipsum Sit Dolor",
      "description": "Fresh salad with grilled chicken breast, mixed greens, and light dressing",
      "macros": {{
        "calories": 450,
        "protein": 35,
        "carbs": 30,
        "fat": 15
      }},
      "restaurant": {{
        "name": "Lorem Ipsum",
        "location": "123 Main St, Finchley, N3 3EB"
      }}
    }}
  ]
}}
Respond ONLY with the JSON object, nothing else before or after."""

    def _parse_response(self, content: str) -> List[MealSuggestion]:
        """Parse the API response into meal suggestion objects.

        Args:
            content: Raw response content from OpenAI API

        Returns:
            List of parsed meal suggestions

        Raises:
            AIServiceError: If the response cannot be properly parsed
        """
        try:
            response_data = json.loads(content)

            if "meals" not in response_data:
                raise LLMServiceError("Response does not contain 'meals' property")

            suggestions_data = response_data["meals"]

            suggestions = []
            for item in suggestions_data:
                suggestion = MealSuggestion(**item)
                suggestions.append(suggestion)

            return suggestions

        except json.JSONDecodeError:
            raise LLMServiceError("Failed to parse JSON response")
        except Exception as e:
            raise LLMServiceError(f"Failed to parse meal suggestions: {str(e)}")


meal_llm_service = MealLLMService()
