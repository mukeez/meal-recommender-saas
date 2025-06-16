"""AI service for generating meal suggestions.

This module provides functions to interact with the MealLLMService
to generate meal suggestions based on user requirements.
"""
import logging
import json
from typing import Optional, List, Dict, Any
import openai

from app.core.config import settings
from app.models.meal import MealSuggestion, MealSuggestionRequest, MealSuggestionResponse
from app.services.base_llm_service import BaseLLMService, LLMServiceError
import traceback
import random

logger = logging.getLogger(__name__)
class MealLLMService(BaseLLMService):
    """AI service for generating meal suggestions based on user requirements."""

    def __init__(self, request: MealSuggestionRequest, restaurants: Optional[List[Dict[str, Any]]] = []):
        """Initialize the MealLLMService with request and optional restaurant data.
        Args:
            request: The meal suggestion request containing user preferences
            restaurants: Optional list of restaurant data to use in meal suggestions
        """
        self.request = request
        self.restaurants = restaurants

        super().__init__()

    async def _send_request(
        self, system_prompt, prompt, max_tokens=2000, temperature=0.5
    ):
        """
        Send a request to the AI service and return the raw response.
        Args:
            system_prompt: The system prompt to set the context for the AI.
            prompt: The user input to generate a response for.
            max_tokens: Maximum number of tokens in the response.
            temperature: Sampling temperature for response variability.
        Returns:
            The raw response content from the AI service.
        """
        try:
            response = self.client.responses.parse(
                    model=settings.MODEL_NAME,
                    input=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {"role": "user", "content": prompt},
                    ],
                    text_format=MealSuggestionResponse)
            return response.output_parsed
        except openai.OpenAIError as e:
            raise LLMServiceError(f"OpenAI API error: {e}")

    async def get_meal_suggestions(self) -> MealSuggestionResponse:
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
            system_prompt = """You are a nutrition expert and restaurant knowledge specialist. Provide accurate, concise meal suggestions based on the user's macro requirements. You **must** suggest between 5-8 meal options, ensuring they are from the specified restaurants or locations. """

            if self.restaurants:
                temperature = 0.5
            else:
                temperature = 0.0
            
            suggestions = await self.generate_response(
                system_prompt=system_prompt, request=self.request, temperature=temperature, should_parse=False
            )
            return suggestions
        except openai.OpenAIError as e:
            raise LLMServiceError(f"OpenAI API error: {str(e)}")
        except json.JSONDecodeError:
            raise LLMServiceError("Failed to parse AI response as JSON")
        except Exception as e:
            raise LLMServiceError(f"Unexpected error: {str(e)}")

    def _build_prompt(self, request: MealSuggestionRequest) -> str:
        """Build a prompt for the OpenAI API based on available restaurant data.
        
        Args:
            request: The meal suggestion request
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""Suggest between 5 and 8 meal options"""

        
        # Conditional part based on restaurant availability
        if self.restaurants:
            prompt += f"""from the following restaurants that can help me meet these macro requirements:
                    - Calories: {request.calories} kcal
                    - Protein: {request.protein} g
                    - Carbs: {request.carbs} g
                    - Fat: {request.fat} g"""
        else:
            prompt += f"""from restaurants in {request.location} that can help me meet these macro requirements:
                    - Calories: {request.calories} kcal
                    - Protein: {request.protein} g
                    - Carbs: {request.carbs} g
                    - Fat: {request.fat} g"""
        
        # Add dietary preference if provided
        if request.dietary_preference:
            prompt += f"\n- Dietary Preference: {request.dietary_preference}"

        # Add dietary restrictions if provided
        if request.dietary_restrictions and len(request.dietary_restrictions) > 0:
            restrictions_str = ", ".join(request.dietary_restrictions)
            prompt += f"\n - Dietary Restrictions: {restrictions_str}"

        if self.restaurants:
            prompt += f"""
                    <restaurants>
                        {self._format_restaurants_for_prompt(self.restaurants)}
                    </restaurants>"""
        
        # Common part for all prompts
        prompt += f"""
                    For each meal suggestion, provide:
                    1. Meal name
                    2. Brief description
                    3. Estimated macros (calories, protein, carbs, fat) — note these can be approximate
                    4. Restaurant name and location

                    Format your response as a JSON object with a "meals" property containing an array of meal objects. Each meal object should include:
                    - name (string)
                    - description (string)
                    - macros (object) with numeric values for "calories", "protein", "carbs", "fat"
                    - restaurant (object) with "name" and "location" properties"""
        
        if self.restaurants:
            prompt += """
                    Only suggest meals from the provided restaurants."""
        else:
            prompt += f"""
                    Only suggest restaurants that exist in {request.location}."""
        
        prompt += f"""
                    Example format (do not use these values, please suggest real meals (between 5 and 8 meals) and check if these name and location exist near {request.location} else do not return in json):
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
    
        return prompt



    def _format_restaurants_for_prompt(self, restaurants: List[Dict[str, Any]]) -> str:
        """Format restaurant data for inclusion in the prompt.
        Args:
            restaurants: List of restaurant data dictionaries
        Returns:
            Formatted string with restaurant details
        """
        restaurants_text = ""
        
        # Determine the number of restaurants to select (at most 5)
        num_to_select = min(len(restaurants), 5)
        
        # Randomly select restaurants if there are more than 0
        if num_to_select > 0:
            selected_restaurants = random.sample(restaurants, num_to_select)
        else:
            selected_restaurants = []

        for i, restaurant in enumerate(selected_restaurants, 1):
            restaurants_text += f"\nRestaurant {i}: {restaurant.get('name', '')}\n"
            restaurants_text += f"- Address: {restaurant.get('address', '')}\n"
            
            if restaurant.get('website'):
                restaurants_text += f"- Website: {restaurant.get('website', '')}\n"
            
            if restaurant.get('menu_url'):
                restaurants_text += f"- Menu URL: {restaurant.get('menu_url', '')}\n"
            
            # Add menu items if available
            if restaurant.get('menu_items'):
                try:
                    # Parse menu items from JSON string if needed
                    menu_items = restaurant['menu_items']
                    if isinstance(menu_items, str):
                        menu_items = json.loads(menu_items)
                    
                    if menu_items and len(menu_items) > 0:
                        restaurants_text += "- Menu Items:\n"
                        
                        # Randomly select up to 5 menu items
                        sample_size = min(5, len(menu_items))
                        selected_items = random.sample(menu_items, sample_size)
                        
                        for item in selected_items:
                            if isinstance(item, dict):
                                name = item.get('name', '')
                                description = item.get('description', '')
                                
                                if name:
                                    restaurants_text += f"  * {name}\n"
                                    if description:
                                        restaurants_text += f"    {description}\n"
                except Exception as e:
                    logger.error(f"Error processing menu items: {e}")
            
            restaurants_text += "\n"
        
        return restaurants_text


meal_llm_service = MealLLMService
