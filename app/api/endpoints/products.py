"""API endpoints for retrieving products."""

import logging
import traceback
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.api.auth_guard import auth_guard
from app.models.product import ProductList, ProductSearchResponse, ProductNutritionResponse, ProductWithNutrition
from app.models.meal import LoggedMeal, MealSearchResponse, MealType, LoggingMode, ServingUnitEnum, LoggedMealWithBarcode, ProductMealSearchResponse
from app.services.product_service import product_service
from app.services.openfoodfacts_service import openfoodfacts_service

logger = logging.getLogger(__name__)

router = APIRouter()


def convert_product_to_logged_meal(product) -> LoggedMealWithBarcode:
    """Convert a Product object to a LoggedMealWithBarcode object.
    
    Args:
        product: Product object to convert
        
    Returns:
        LoggedMealWithBarcode object with product data
    """
    # Get nutrition facts from the product (prefer verified over AI-generated)
    nutrition = product.nutrition_facts or product.gpt_nutrition_facts
    
    # Extract nutrition values with defaults
    calories = int(nutrition.calories) if nutrition and nutrition.calories else 0
    protein = float(nutrition.protein) if nutrition and nutrition.protein else 0.0
    carbs = float(nutrition.carbs) if nutrition and nutrition.carbs else 0.0
    fat = float(nutrition.fat) if nutrition and nutrition.fat else 0.0
    amount = float(nutrition.amount) if nutrition and nutrition.amount else 100.0
    serving_unit = nutrition.serving_unit if nutrition and nutrition.serving_unit else "grams"
    
    # Create LoggedMealWithBarcode object
    return LoggedMealWithBarcode(
        id=str(uuid.uuid4()),  # Generate unique ID
        name=product.product_name or "Unknown Product",
        description=f"{product.brand_name} - {product.product_name}" if product.brand_name else product.product_name,
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat,
        meal_time=None,
        meal_type=None,
        logging_mode=LoggingMode.BARCODE,
        photo_url=None,
        created_at=None,
        notes=f"Ingredients: {product.ingredients}" if product.ingredients else None,
        serving_unit=ServingUnitEnum(serving_unit) if serving_unit in [e.value for e in ServingUnitEnum] else ServingUnitEnum.GRAMS,
        amount=amount,
        read_only=True,
        favorite=False,
        barcode=product.barcode
    )


@router.get(
    "/search",
    response_model=ProductNutritionResponse,
    response_model_by_alias=False,
    status_code=status.HTTP_200_OK,
    summary="Get nutrition facts for similar products",
    description="Get nutrition facts for similar products that match the query",
)
async def product_search(
    query: str = Query(
        ..., description="Product to search can be product name or brand name"
    ),
    page: int = Query(1, description="Current page number defaults to 1"),
    page_size: int = Query(
        20, description="Number of products to include on each page defaults to 20"
    ),
    user=Depends(auth_guard),
) -> ProductNutritionResponse:
    """Get paginated list of similar products.

    This endpoint retrieves a paginated list of similar products that match the query

    Args:
        query: The product to search can be product name or brand name
        page: The current page number defaults to 1
        page_size: The number of products to include on each page defaults to 20
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        A list of paginated products

    Raises:
        HTTPException: If there is an error processing the request
    """
    try:
        logger.info(
            f"product search:[query:{query}][page:{page}][page_size:{page_size}]"
        )
        # get list of products from database
        products = await product_service.get_products(
            product_name=query, page=page, page_size=page_size
        )
        if not products:
            # get results from openfoodfacts
            products = await openfoodfacts_service.product_search(
                product=query, page=1, page_size=page_size
            )

            # upsert products (skip for now due to type issues)
            # await product_service.upsert_product(products.products)

        # Convert products to ProductWithNutrition (merge nutrition facts)
        products_with_nutrition = []
        if products and products.products:
            for product in products.products:
                # Use nutrition_facts if available, otherwise use gpt_nutrition_facts
                merged_nutrition = product.nutrition_facts or product.gpt_nutrition_facts
                
                product_with_nutrition = ProductWithNutrition(
                    barcode=product.barcode,
                    product_name=product.product_name,
                    brand_name=product.brand_name,
                    ingredients=product.ingredients,
                    nutrition_facts=merged_nutrition
                )
                products_with_nutrition.append(product_with_nutrition)

        return ProductNutritionResponse(
            products=products_with_nutrition,
            total_products=products.count if products else 0,
            search_query=query
        )

    except HTTPException:
        traceback.print_exc()
        raise

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving products: {str(e)}",
        )


@router.get(
    "/search-meals-format",
    response_model=ProductMealSearchResponse,
    response_model_by_alias=False,
    status_code=status.HTTP_200_OK,
    summary="Search products with meal search compatible format",
    description="Search for products and return results in the same format as meal search with barcode",
)
async def product_search_meals_format(
    query: str = Query(
        ..., description="Product to search can be product name or brand name"
    ),
    page: int = Query(1, description="Current page number defaults to 1"),
    page_size: int = Query(
        20, description="Number of products to include on each page defaults to 20"
    ),
    user=Depends(auth_guard),
) -> ProductMealSearchResponse:
    """Search for products and return results in meal search compatible format.

    This endpoint retrieves products that match the query and returns them
    in the same format as the meal search endpoint for consistency.

    Args:
        query: The product to search can be product name or brand name
        page: The current page number defaults to 1
        page_size: The number of products to include on each page defaults to 20
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        MealSearchResponse with products converted to LoggedMeal format

    Raises:
        HTTPException: If there is an error processing the request
    """
    try:
        user_id = user.get("sub")
        
        logger.info(
            f"product search meals format:[query:{query}][page:{page}][page_size:{page_size}]"
        )
        # get list of products from database
        products = await product_service.get_products(
            product_name=query, page=page, page_size=page_size
        )
        if not products:
            # get results from openfoodfacts
            products = await openfoodfacts_service.product_search(
                product=query, page=1, page_size=page_size
            )

            # upsert products (skip for now due to type issues)
            # await product_service.upsert_product(products.products)

        # Convert products to LoggedMeal format
        logged_meals = []
        if products and products.products:
            for product in products.products:
                try:
                    logged_meal = convert_product_to_logged_meal(product)
                    logged_meals.append(logged_meal)
                except Exception as e:
                    logger.warning(f"Failed to convert product to logged meal: {e}")
                    # Continue with other products

        # Return in meal search compatible format with barcodes
        return ProductMealSearchResponse(
            results=logged_meals,
            total_results=products.count if products else 0,
            search_query=query
        )

    except HTTPException:
        traceback.print_exc()
        raise

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving products: {str(e)}",
        )
