"""LLM service for processing web search results into product information.

This module provides an LLM service that takes web search results and extracts
structured product information including nutrition facts.
"""

import logging
import json
from typing import Dict, Any, List, Optional

from app.services.base_llm_service import BaseLLMService, LLMServiceError
from app.models.product import Product, NutritionFacts

logger = logging.getLogger(__name__)


class WebSearchLLMService(BaseLLMService):
    """LLM service for processing web search results into product data."""

    def __init__(self):
        super().__init__()

    def _build_prompt(self, request: Dict[str, Any]) -> str:
        """Build prompt for extracting product information from search results.
        
        Args:
            request: Dictionary containing barcode and search_results
            
        Returns:
            Formatted prompt string
        """
        barcode = request.get("barcode", "")
        search_results = request.get("search_results", [])
        
        # Format search results for the prompt
        search_context = ""
        for i, result in enumerate(search_results[:5], 1):  # Use top 5 results
            title = result.get("title", "")
            content = result.get("content", "")
            url = result.get("url", "")
            
            search_context += f"""
Result {i}:
Title: {title}
Content: {content}
URL: {url}
---
"""

        return f"""You are an expert at extracting product information from web search results. 

Given the barcode "{barcode}" and the following web search results, extract the product information:

{search_context}

Based on these search results, provide the following product information:

1. **Product Name**: The full product name
2. **Brand Name**: The manufacturer/brand name  
3. **Ingredients**: List of ingredients (if available)
4. **Barcode**: Use the provided barcode "{barcode}"
5. **Nutrition Facts**: Estimated nutrition information per 100 grams

For nutrition facts, provide:
- **Name**: Product name
- **Amount**: 100 (always use 100 grams as standard)
- **Serving Unit**: "grams" 
- **Calories**: Estimated calories per 100g
- **Protein**: Estimated protein in grams per 100g
- **Carbs**: Estimated carbohydrates in grams per 100g  
- **Fat**: Estimated fat in grams per 100g

IMPORTANT: 
- If you cannot find specific nutrition information, provide reasonable estimates based on similar products
- Always use 100 grams as the serving amount for consistency
- Extract ingredients text if available in the search results
- Be conservative with nutrition estimates if uncertain

Format your response as a valid JSON object with this structure:
{{
  "barcode": "{barcode}",
  "product_name": "Product Name",
  "brand_name": "Brand Name", 
  "ingredients": "Ingredient list text or null if not available",
  "nutrition_facts": {{
    "name": "Product Name",
    "amount": 100,
    "serving_unit": "grams",
    "calories": number,
    "protein": number,
    "carbs": number,
    "fat": number
  }}
}}"""

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM response into structured product data.
        
        Args:
            content: Raw LLM response
            
        Returns:
            Parsed product data dictionary
        """
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise LLMServiceError(f"Failed to parse response as JSON: {e}")

    async def extract_product_from_search_results(
        self, 
        barcode: str, 
        search_results: List[Dict[str, Any]],
        user_id: str = None
    ) -> Product:
        """Extract product information from web search results using LLM.
        
        Args:
            barcode: Product barcode
            search_results: List of web search result dictionaries
            user_id: Optional user ID for tracking
            
        Returns:
            Product object with extracted information
            
        Raises:
            LLMServiceError: If extraction fails
        """
        try:
            logger.info(f"Extracting product info from {len(search_results)} search results for barcode: {barcode}")
            
            request_data = {
                "barcode": barcode,
                "search_results": search_results
            }
            
            # Use LLM to extract product information
            system_prompt = "You are an expert at extracting structured product information from web search results. Always provide accurate and consistent nutrition data."
            
            result = await self.generate_response(
                system_prompt=system_prompt,
                request=request_data,
                max_tokens=1000,
                temperature=0.2,  # Low temperature for consistency
                user_id=user_id
            )
            
            # Create Product object from the result
            product_data = {
                "barcode": result["barcode"],
                "product_name": result["product_name"],
                "brand_name": result.get("brand_name"),
                "ingredients": result.get("ingredients")
            }
            
            # Create nutrition facts
            nutrition_data = result["nutrition_facts"]
            nutrition_facts = NutritionFacts(**nutrition_data)
            
            # Create product with nutrition facts
            product = Product(**product_data)
            product.nutrition_facts = nutrition_facts
            
            logger.info(f"Successfully extracted product info for barcode: {barcode}")
            return product
            
        except (KeyError, TypeError) as e:
            logger.error(f"Invalid response structure from LLM: {e}")
            raise LLMServiceError(f"Invalid response structure: {e}")
        except Exception as e:
            logger.error(f"Error extracting product from search results: {e}")
            raise LLMServiceError(f"Failed to extract product information: {e}")


web_search_llm_service = WebSearchLLMService()