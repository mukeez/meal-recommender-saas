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
from app.services.user_service import user_service
import traceback
import random

logger = logging.getLogger(__name__)

class MealLLMService(BaseLLMService):
    """AI service for generating meal suggestions based on user requirements."""

    def __init__(self, request: MealSuggestionRequest, user_id: str, restaurants: Optional[List[Dict[str, Any]]] = []):
        """Initialize the MealLLMService with request, user_id and optional restaurant data.
        Args:
            request: The meal suggestion request containing user preferences
            user_id: The user ID to fetch dietary preferences from database
            restaurants: Optional list of restaurant data to use in meal suggestions
        """
        super().__init__()
        self.request = request
        self.user_id = user_id
        self.restaurants = restaurants
        self.user_preferences = None

    async def _fetch_user_preferences(self) -> Dict[str, Any]:
        """Fetch user dietary preferences from the database.
        
        Returns:
            Dictionary containing user preferences including dietary_restrictions and dietary_preference
        """
        try:
            if not self.user_preferences:
                self.user_preferences = await user_service.get_user_preferences(self.user_id)
            return self.user_preferences
        except Exception as e:
            logger.warning(f"Could not fetch user preferences for user {self.user_id}: {str(e)}")
            return {}

    def _parse_response(self, content: str) -> MealSuggestionResponse:
        """
        Parse raw AI output into a MealSuggestionResponse object.
        """
        try:
            data = json.loads(content)
            return MealSuggestionResponse(**data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse meal suggestion response: {e}")
            raise LLMServiceError(f"Failed to parse meal suggestion response: {e}")

    async def get_meal_suggestions(self) -> MealSuggestionResponse:
        """Get meal suggestions from OpenAI API.

        Returns:
            List of meal suggestions that match the user's criteria

        Raises:
            LLMServiceError: If there is an error communicating with the API
                            or processing the response
        """
        try:
            system_prompt = """You are a nutrition expert. Based on the user's macro requirements, suggest 5-8 accurate, easy-to-make, and concise meal options """

            if self.restaurants:
                temperature = 0.5
            else:
                temperature = 0.0
            
            suggestions = await self.generate_response(
                system_prompt=system_prompt,
                request=self.request,
                temperature=temperature,
                user_id=self.user_id,
            )
            return suggestions
        except LLMServiceError as e:
            raise e
        except Exception as e:
            raise LLMServiceError(f"Unexpected error in get_meal_suggestions: {str(e)}")

    async def _build_prompt(self, request: MealSuggestionRequest) -> str:
        """Build a prompt for the OpenAI API based on available restaurant data.
        
        Args:
            request: The meal suggestion request
            
        Returns:
            Formatted prompt string
        """
        # Fetch user preferences from database
        user_prefs = await self._fetch_user_preferences()

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
        
        # Add dietary preference from database if available
        dietary_preference = user_prefs.get('dietary_preference')
        if dietary_preference:
            prompt += f"\n- Dietary Preference: {dietary_preference}"

        # Add dietary restrictions from database if available
        dietary_restrictions = user_prefs.get('dietary_restrictions', [])
        if dietary_restrictions and len(dietary_restrictions) > 0:
            restrictions_str = ", ".join(dietary_restrictions)
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
                    5. Match score (0-100%) - Calculate this based on:
                       - How closely the meal's macros align with the target macros (higher score for closer matches)
                       - Adherence to dietary restrictions (meals that violate restrictions should receive very low scores 0-30%)
                       - Compatibility with dietary preferences (meals that align well should get higher scores)
                       - Account for macro overages and shortages (significant overages or shortages should reduce the score)
                       - Perfect matches should score 90-100%, good matches 70-89%, fair matches 50-69%, poor matches 30-49%, incompatible meals 0-29%

                    Format your response as a JSON object with a "meals" property containing an array of meal objects. Each meal object should include:
                    - name (string)
                    - description (string)
                    - macros (object) with numeric values for "calories", "protein", "carbs", "fat"
                    - restaurant (object) with "name" and "location" properties
                    - match_score (integer from 0-100)"""
        
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
                        }},
                        "match_score": 85
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


    async def generate_response(
        self,
        system_prompt: str,
        request: Any,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        **kwargs
    ) -> Any:
        """
        Override the base generate_response to handle async _build_prompt.

        Args:
            system_prompt: The system prompt
            request: The request object
            max_tokens: Maximum tokens
            temperature: Temperature setting
            **kwargs: Additional arguments

        Returns:
            A parsed response generated by the AI service
        """
        should_parse = kwargs.get("should_parse", True) 

        prompt = await self._build_prompt(request)  # Now async
        raw = await self._send_request(
            system_prompt=system_prompt,
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if not should_parse:
            return raw
        return self._parse_response(raw)
        

meal_llm_service = MealLLMService
