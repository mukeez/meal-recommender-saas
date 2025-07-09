"""OpenFoodFacts service for generating nutritional information and performing product search.

This module provides functions to interact with the OpenFoodFacts API and OpenAI
to perform product search and generate nutritional information
"""

import logging
from typing import Optional

from fastapi import HTTPException
from app.core.config import settings
from app.models.product import Product, ProductList, NutritionFacts
from app.services.base_llm_service import BaseLLMService, LLMServiceError
from app.utils.constants import normalize_nutrition_to_per_gram, parse_gram_quantity

import openfoodfacts
import openai
from openai import OpenAI

import asyncio
import json

logger = logging.getLogger(__name__)

# Note: All serving units are converted to grams for consistency

def convert_to_standard_grams(quantity: float, unit: str) -> float:
    """Convert quantity to grams based on the unit.
    
    Args:
        quantity: The quantity value
        unit: The unit symbol (g, kg, mg, etc.)
        
    Returns:
        Quantity converted to grams
    """
    if unit == 'kg':
        return quantity * 1000
    elif unit == 'mg':
        return quantity / 1000
    elif unit in ['ml', 'cl']:
        # Assume 1ml = 1g for simplicity with liquids
        if unit == 'cl':
            return quantity * 10  # 1cl = 10ml = 10g
        return quantity  # 1ml = 1g
    elif unit == 'l':
        return quantity * 1000  # 1l = 1000ml = 1000g
    elif unit == 'oz':
        return quantity * 28.3495  # 1oz = 28.3495g
    elif unit == 'lb':
        return quantity * 453.592  # 1lb = 453.592g
    else:
        # Default to grams or return as-is
        return quantity


class OpenFoodFactsService(BaseLLMService):
    def __init__(self):
        """Initialize UserAgent for openfoodfacts api"""
        self.api = openfoodfacts.API(user_agent="meal-saas/1.0")
        super().__init__()

    async def scan_barcode(self, barcode: str) -> Product:
        """
        Scan a product barcode and return a fully populated Product.

        This method uses the OpenFoodFacts API to look up product info and nutrition data.
        If nutrition data is available from OpenFoodFacts, it uses that; otherwise falls back to LLM.

        Args:
            barcode (str): The barcode string identifying the product.

        Returns:
            Product: A Product instance including product_name, brands,
                ingredients_text, and nutrition facts.

        Raises:
            LLMServiceError: If the product lookup or nutrition-fetching
                operation fails.
        """
        try:
            # Get product with nutritional information and serving data
            result = self.api.product.get(
                code=barcode, 
                fields=[
                    "product_name", "brands", "ingredients_text", 
                    "nutriments", "serving_quantity", "serving_quantity_unit"
                ]
            )
            if not result:
                raise HTTPException(status_code=404, detail="Item not found")
            
            result["code"] = barcode
            product = Product(**result)
            
            # Try to extract nutrition facts from OpenFoodFacts data
            nutrition_facts = self._extract_nutrition_facts_from_api(result)
            
            if nutrition_facts:
                # Use the real nutrition data from OpenFoodFacts
                product.nutrition_facts = nutrition_facts
                logger.info(f"Using verified nutrition data from OpenFoodFacts for barcode: {barcode}")
            else:
                # Fall back to LLM-generated nutrition facts
                product = await self.get_nutrition_facts(product)
                logger.info(f"Using LLM-generated nutrition data for barcode: {barcode}")
            
            return product
            
        except HTTPException:
            # Re-raise HTTP exceptions without modification
            raise
        except Exception as e:
            logger.error(f"Failed to get product with error : {e}")
            raise LLMServiceError("Failed to get product")

    async def product_search(
        self, product: str, page: int = 1, page_size: int = 20
    ) -> ProductList:
        """Search for similar products

        Args:
            product (str): A product with barcode, product_name and brand_name
            page (int, optional): Current page number. Defaults to 1.
            page_size (int, optional): The number of products to include on each page. Defaults to 20.

        Raises:
            LLMServiceError: Raised when there's an error generating a response

        Returns:
            ProductList: A paginated list of products
        """
        try:
            products = []

            logger.info(f"Searching for products with product: {product}, page: {page}, page_size: {page_size}")
            results = self.api.product.text_search(
                product, page=page, page_size=page_size
            )
            if not results:
                return ProductList(products=[], count=0, page=page, page_size=page_size)
                
            for result in results["products"]:
                try:
                    # Create product and try to get real nutrition data
                    product_obj = Product(**result)
                    
                    # Try to extract nutrition facts from search result
                    nutrition_facts = self._extract_nutrition_facts_from_api(result)
                    
                    if nutrition_facts:
                        # Use the real nutrition data from OpenFoodFacts
                        product_obj.nutrition_facts = nutrition_facts
                    else:
                        # Fall back to LLM-generated nutrition facts
                        product_obj = await self.get_nutrition_facts(product_obj)
                        
                    products.append(product_obj)
                except Exception as e:
                    logger.warning(f"Failed to process product in search results: {e}")
                    pass
                    
            return ProductList(
                products=products,
                count=results["count"],
                page=results["page"],
                page_size=results["page_size"],
            )
        except Exception as e:
            logger.error(f"Failed to product search with error : {e}")
            raise LLMServiceError("Failed to perform product search")

    async def get_nutrition_facts(self, product: Product) -> Product:
        """Get the nutritional information for a given  product

        Args:
            product (Product): A product with barcode, product_name and brand_name

        Raises:
            LLMServiceError: Raised when there's an error generating a response

        Returns:
            Product: An updated product object with nutrition_facts
        """
        try:
            system_prompt = "You are an expert at providing nutritional information for food items. Given a food item specified by its brand name and a list of its ingredients, provide the estimated nutritional information and typical serving quantity."
            response = await self.generate_response(
                system_prompt=system_prompt, request=product, temperature=0.2
            )
            product.gpt_nutrition_facts = response
            return product
        except openai.OpenAIError as e:
            raise LLMServiceError(f"OpenAI API error: {str(e)}")
        except json.JSONDecodeError:
            raise LLMServiceError("Failed to parse AI response as JSON")
        except Exception as e:
            raise LLMServiceError(f"Unexpected error: {str(e)}")

    def _build_prompt(self, product: Product) -> str:
        """build prompt for OpenAI

        Args:
            product (Product): A product with barcode, product_name and brand_name

        Returns:
            str: formatted prompt string
        """

        return f"""
            For the food item with the brand name: {product.brand_name}, product_name: {product.product_name} and the following ingredients: {product.ingredients}, please provide the following information:
            1. **Name of the Food**: (As it would typically be recognized)
            2. **Estimated Amount:** (Provide as a numeric value representing a typical serving size in grams, e.g., 100, 250, 30)
            3. **Serving Unit:** (Always use "grams" for consistency)
            4. **Estimated Calories:** (in kcal or Cal per the specified gram amount)
            5. **Estimated Protein:** (in grams per the specified gram amount)
            6. **Estimated Carbohydrates:** (in grams per the specified gram amount)
            7. **Estimated Fat:** (in grams per the specified gram amount)

            IMPORTANT: All nutritional values should correspond to the gram amount you specify. For example, if you specify amount: 100, then provide calories, protein, carbs, and fat for 100 grams of the product.

            Format your response as a valid JSON object with the following structure:

            ```json
            {{
                "name": "Name of the Food",
                "amount": number,
                "serving_unit": "grams",
                "calories": number,
                "protein": number,
                "carbs": number,
                "fat": number
            }}
            """

    def _parse_response(self, content: str) -> NutritionFacts:
        """
            Parse OpenAI response into NutritionFacts
        Args:
            content (str): Generated response by OpenAI

        Raises:
            LLMServiceError: Raised when there's an error generating a response

        Returns:
            NutritionFacts: Nutritional information of a product
        """
        try:
            response = json.loads(content)
            return NutritionFacts(**response)
        except json.JSONDecodeError:
            raise LLMServiceError("Failed to decode json response")
        except Exception as e:
            logger.error(f"Failed to parse response with error: {e}")
            raise LLMServiceError(f"Failed to parse response with error: {e}")

    def _extract_nutrition_facts_from_api(self, api_result: dict) -> Optional[NutritionFacts]:
        """Extract nutrition facts from OpenFoodFacts API result.
        
        Args:
            api_result: The API response from OpenFoodFacts
            
        Returns:
            NutritionFacts object if nutrition data is available, None otherwise
        """
        try:
            nutriments = api_result.get("nutriments")
            serving_quantity = api_result.get("serving_quantity")
            serving_quantity_unit = api_result.get("serving_quantity_unit", "g")
            
            # Check if we have nutriments data
            if not nutriments or not isinstance(nutriments, dict):
                logger.warning("No nutriments data in OpenFoodFacts response")
                return None
                
            # Check if we have the essential nutrition data
            required_keys = ["carbohydrates_serving", "proteins_serving", "fat_serving", "energy-kcal_serving"]
            if not all(key in nutriments for key in required_keys):
                logger.warning("Missing essential nutrition data in OpenFoodFacts response")
                return None
            
            # Extract nutrition values per serving
            nutriments_dict = nutriments  
            carbs_serving = float(nutriments_dict["carbohydrates_serving"])
            protein_serving = float(nutriments_dict["proteins_serving"])
            fat_serving = float(nutriments_dict["fat_serving"])
            calories_serving = float(nutriments_dict["energy-kcal_serving"])
            
            # Get serving information
            if serving_quantity is None or serving_quantity <= 0:
                logger.warning("Invalid or missing serving_quantity in OpenFoodFacts response")
                return None
                
            serving_quantity = float(serving_quantity)
            
            # Convert serving quantity to grams if needed
            serving_grams = convert_to_standard_grams(serving_quantity, serving_quantity_unit)
            
            # Create the nutrition facts with serving data
            nutrition_facts = NutritionFacts(
                name=api_result.get("product_name", "Unknown Product"),
                calories=int(calories_serving),
                protein=protein_serving,
                carbs=carbs_serving, 
                fat=fat_serving,
                amount=serving_grams,
                serving_unit="grams"  # Always standardized to grams
            )
            
            logger.info(f"Extracted nutrition facts: {serving_grams:.1f}g with {calories_serving} cal, {protein_serving}g protein, {carbs_serving}g carbs, {fat_serving}g fat")
            return nutrition_facts
            
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Error extracting nutrition facts from API result: {e}")
            return None


openfoodfacts_service = OpenFoodFactsService()
