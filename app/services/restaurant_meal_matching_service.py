"""Service for matching meals to restaurants based on user preferences.

This module provides LLM-based meal suggestions for restaurants
using cuisine types and user macro targets.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from app.services.base_llm_service import BaseLLMService, LLMServiceError

logger = logging.getLogger(__name__)


class RestaurantMealMatchingService(BaseLLMService):
    """Service for generating meal recommendations for restaurants."""
    
    def __init__(self):
        super().__init__()
    
    def _extract_cuisine_from_types(self, place_types: List[str]) -> str:
        """Extract cuisine type from Google Places types.
        
        This is a simple helper that tries to identify obvious cuisine types.
        The LLM will do the heavy lifting of inferring cuisine from place types.
        
        Args:
            place_types: List of place types from Google Places
            
        Returns:
            Cuisine type string or "restaurant" as fallback
        """
        # Just pass the types to LLM - it will infer the cuisine
        # Return first type that looks like a cuisine, otherwise "restaurant"
        for place_type in place_types:
            if "_restaurant" in place_type:
                # Extract cuisine name: "italian_restaurant" -> "Italian"
                cuisine = place_type.replace("_restaurant", "").replace("_", " ").title()
                return cuisine
        
        # Default fallback - LLM will infer from restaurant name and types
        return "restaurant"
    
    def filter_by_meal_name(
        self,
        meal: Dict[str, Any],
        search_query: Optional[str]
    ) -> bool:
        """Check if meal name matches search query.
        
        Args:
            meal: Meal dictionary with 'name' field
            search_query: Search term to match against
            
        Returns:
            True if no query or match found, False otherwise
        """
        if not search_query:
            return True  # No filter, include all meals
        
        meal_name = meal.get("name", "").lower()
        query_lower = search_query.lower()
        
        # Case-insensitive partial match
        matches = query_lower in meal_name
        
        if not matches:
            logger.info(f"Meal '{meal_name}' filtered out (doesn't match '{search_query}')")
        
        return matches
    
    def _build_prompt(self, request: Dict[str, Any]) -> str:
        """Build LLM prompt for meal suggestion.
        
        Args:
            request: Dictionary containing restaurant and user data
            
        Returns:
            Formatted prompt string
        """
        restaurant_name = request.get("restaurant_name", "Unknown")
        place_types = request.get("place_types", [])
        macro_targets = request.get("macro_targets", {})
        dietary_restrictions = request.get("dietary_restrictions", [])
        dietary_preference = request.get("dietary_preference")
        
        # Let LLM infer cuisine from place types and name
        prompt = f"""You are a nutrition expert. Based on the restaurant name and categories provided, infer the cuisine type and suggest ONE typical meal that matches user requirements.

Restaurant Details:
- Name: {restaurant_name}
- Google Places Categories: {', '.join(place_types)}

IMPORTANT: Infer the cuisine type from the restaurant name and categories above. Examples:
- "italian_restaurant" → Italian cuisine → suggest pasta, pizza, etc.
- "chinese_restaurant" → Chinese cuisine → suggest fried rice, noodles, etc.
- "mexican_restaurant" → Mexican cuisine → suggest tacos, burritos, etc.
- "cafe", "restaurant" → Infer from restaurant name

User Requirements:
- Target Calories: {macro_targets.get('calories', 'no preference')} kcal
- Target Protein: {macro_targets.get('protein', 'no preference')}g
- Target Carbs: {macro_targets.get('carbs', 'no preference')}g
- Target Fat: {macro_targets.get('fat', 'no preference')}g
"""
        
        if dietary_restrictions:
            prompt += f"- Dietary Restrictions: {', '.join(dietary_restrictions)}\n"
        
        if dietary_preference:
            prompt += f"- Dietary Preference: {dietary_preference}\n"
        
        prompt += """
Task:
1. Infer the cuisine type from the restaurant name and categories
2. Suggest ONE typical meal from that cuisine type
3. Provide estimated macros for a standard serving
4. Calculate match score (0-100%) based on:
   - Macro alignment: ±20% = 90-100%, ±40% = 70-89%, ±60% = 50-69%, >60% = 0-49%
   - Dietary compliance: Violation = automatic 0%
   - Reasonable portion size for the cuisine

Rules:
- Be specific to the inferred cuisine type
- Use realistic serving sizes
- If dietary restrictions conflict with typical dishes, score MUST be 0
- Match score must reflect BOTH macro fit AND dietary compliance
- Description must be under 150 characters

Return ONLY valid JSON:
{
  "name": "Dish Name",
  "description": "Brief description (max 150 chars)",
  "macros": {
    "calories": <number>,
    "protein": <number>,
    "carbs": <number>,
    "fat": <number>
  },
  "match_score": <0-100>,
  "estimated": true
}
"""
        return prompt
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM response into structured data.
        
        Args:
            content: Raw LLM response
            
        Returns:
            Parsed meal data dictionary
        """
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise LLMServiceError(f"Invalid JSON response: {e}")
    
    async def get_top_meal_for_restaurant(
        self,
        restaurant: Dict[str, Any],
        user_preferences: Dict[str, Any],
        macro_targets: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """Generate top meal suggestion for a restaurant.
        
        Args:
            restaurant: Restaurant data with name, place_types, etc.
            user_preferences: User dietary preferences
            macro_targets: Optional macro targets (calories, protein, carbs, fat)
            
        Returns:
            Meal suggestion with match score
        """
        try:
            # Extract place types
            place_types = restaurant.get("place_types", [])
            
            # Prepare request data (LLM will infer cuisine)
            request_data = {
                "restaurant_name": restaurant.get("name", "Unknown"),
                "place_types": place_types,
                "macro_targets": macro_targets or {},
                "dietary_restrictions": user_preferences.get("dietary_restrictions", []),
                "dietary_preference": user_preferences.get("dietary_preference"),
            }
            
            logger.info(f"Generating meal for {restaurant.get('name')} (types: {', '.join(place_types[:3])})")
            
            # Generate meal via LLM (Helicone caches this automatically)
            meal = await self.generate_response(
                system_prompt="You are a nutrition expert specializing in cuisine-specific meal recommendations. Infer cuisine types from restaurant names and categories.",
                request=request_data,
                temperature=0.3,  # Low for consistency
                max_tokens=500,
                user_id=user_preferences.get("user_id")
            )
            
            return meal
            
        except LLMServiceError as e:
            logger.error(f"LLM error generating meal: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating meal: {e}")
            raise LLMServiceError(f"Failed to generate meal: {e}")


restaurant_meal_matching_service = RestaurantMealMatchingService()
