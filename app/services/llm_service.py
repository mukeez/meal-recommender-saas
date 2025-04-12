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


class LLMServiceError(Exception):
    """Custom exception for AI service errors."""
    pass


class OpenAIService:
    """Service for interacting with OpenAI API."""

    def __init__(self):
        """Initialize the OpenAI client."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.MODEL_NAME

    async def get_meal_suggestions(self, request: MealSuggestionRequest) -> List[MealSuggestion]:
        """Get meal suggestions from OpenAI API.

        Args:
            request: The meal suggestion request containing user preferences

        Returns:
            List of meal suggestions that match the user's criteria

        Raises:
            AIServiceError: If there is an error communicating with the API
                            or processing the response
        """
        try:
            # Construct the prompt for OpenAI
            prompt = self._build_prompt(request)
            # Call the OpenAI API using newer client version
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a nutrition expert and restaurant knowledge specialist. Provide accurate, concise meal suggestions based on the user's macro requirements."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=2000,
                temperature=0.7
            )

            # Extract and parse the response
            content = response.choices[0].message.content
            print(content)
            return self._parse_response(content)

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

Example format (do not use these exact values, please suggest real meals):
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
            # Parse the JSON response
            response_data = json.loads(content)

            # Extract the meals array
            if "meals" not in response_data:
                raise LLMServiceError("Response does not contain 'meals' property")

            suggestions_data = response_data["meals"]

            # Convert raw data to Pydantic models
            suggestions = []
            for item in suggestions_data:
                suggestion = MealSuggestion(**item)
                suggestions.append(suggestion)

            return suggestions

        except json.JSONDecodeError:
            raise LLMServiceError("Failed to parse JSON response")
        except Exception as e:
            raise LLMServiceError(f"Failed to parse meal suggestions: {str(e)}")


# Create a singleton instance
ai_service = OpenAIService()