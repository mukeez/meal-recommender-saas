"""OpenFoodFacts service for generating nutritional information and performing product search.

This module provides functions to interact with the OpenFoodFacts API and OpenAI
to perform product search and generate nutritional information
"""

import logging

from fastapi import HTTPException
from app.core.config import settings
from app.models.product import Product, ProductList, NutritionFacts
from app.services.base_llm_service import BaseLLMService, LLMServiceError

import openfoodfacts
import openai
from openai import OpenAI

import asyncio
import json

logger = logging.getLogger(__name__)


class OpenFoodFactsService(BaseLLMService):
    def __init__(self):
        """Initialize UserAgent for openfoodfacts api"""
        self.api = openfoodfacts.API(user_agent="meal-saas/1.0")
        super().__init__()

    async def scan_barcode(self, barcode: str) -> Product:
        """
        Scan a product barcode and return a fully populated Product.

        This method uses the OpenFoodFacts API to look up basic product info
        (name, brands, ingredients) by barcode, then fetches its nutrition facts.

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
            result = self.api.product.get(
                code=barcode, fields=["product_name", "brands", "ingredients_text"]
            )
            if not result:
                raise HTTPException(status_code=404, detail="Item not found")
            result["code"] = barcode
            # get nutrition facts
            product = await self.get_nutrition_facts(Product(**result))
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
            results = self.api.product.text_search(
                product, page=page, page_size=page_size
            )
            for result in results["products"]:
                try:
                    products.append(Product(**result))
                except:
                    pass
            # get nutrition facts for products
            tasks = [self.get_nutrition_facts(p) for p in products]
            products_with_facts = await asyncio.gather(*tasks)
            return ProductList(
                products=products_with_facts,
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
            2. **Estimated Quantity:** (Provide a common serving size, e.g., "1 serving", "150g", "1 cup". Be as specific as possible based on typical packaging or common usage.)
            3. **Estimated Calories:** (in kcal or Cal)
            4. **Estimated Protein:** (in grams)
            5. **Estimated Carbohydrates:** (in grams)
            6. **Estimated Fat:** (in grams)

            Format your response as a valid JSON object with the following structure:

            ```json
            {{
                "name" : "Name of the Food"
                "quantity": "Quantity",
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


openfoodfacts_service = OpenFoodFactsService()
