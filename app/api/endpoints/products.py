"""API endpoints for retrieving products."""

import logging

from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.api.auth_guard import auth_guard
from app.models.product import ProductList
from app.services.product_service import product_service
from app.services.openfoodfacts_service import openfoodfacts_service
import traceback

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/search",
    response_model=ProductList,
    response_model_by_alias=False,
    status_code=status.HTTP_200_OK,
    summary="Get paginated list of similar products",
    description="Get paginated list of similar products that match the query",
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
) -> ProductList:
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

            # upsert products
            await product_service.upsert_product(products.products)

        return products

    except HTTPException:
        traceback.print_exc()
        raise

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving products: {str(e)}",
        )
