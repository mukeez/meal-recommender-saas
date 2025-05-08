"""Services for managing products.

This module provides functions to perform database operations on products.
"""

from typing import Optional, Union, List
import logging

from fastapi import HTTPException, status
from supabase import create_client
import json

from app.core.config import settings
from app.models.product import Product, LoggedProduct, ProductList, ProductUpdate

logger = logging.getLogger(__name__)


class ProductService:
    """Service for managing products."""

    def __init__(self):
        """Initialize the product service."""
        self.base_url = settings.SUPABASE_URL
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.client = create_client(self.base_url, self.api_key)

    async def log_product(
        self, product: Union[Product, List[Product]]
    ) -> List[LoggedProduct]:
        """Log a product.

        Args:
            product: Details of the product to log. Could be a single product or a list of products

        Returns:
            The logged product
        """
        logger.info(f"Logging product")

        try:
            if isinstance(product, List):
                product_dict = [p.model_dump() for p in product]
            else:
                product_dict = product.model_dump()
            response = (
                self.client.table("products")
                .insert(product_dict)
                .execute()
                .model_dump()
            )
            logged_product_data = response["data"]
            logger.info(f"Product(s) logged successfully")
            logged_products = [LoggedProduct(**item) for item in logged_product_data]
            return logged_products

        except Exception as e:
            logger.error(f"Unexpected error logging product: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error logging product: {str(e)}",
            )

    async def get_products(
        self, product_name: str = None, page: int = 1, page_size: int = 20
    ) -> Optional[ProductList]:
        try:
            """
            Search for products matching the product_name in either the product_name or brand_name fields.
            The search uses a case-insensitive 'like' query.

            Parameters:
                page (int): The current page number (1-indexed).
                page_size (int): The number of records per page.
                product_name (str): The product_name or brand_name for filtering products.

            Returns:
                dict: A dictionary containing the current page, page_size, total count of matching records,
                    and a list of matching products.
            """
            # Build the OR condition query string for both product_name and brand_name using ilike.
            query_str = (
                f"product_name.ilike.%{product_name}%,brand_name.ilike.%{product_name}%"
            )

            # Perform the query.
            response = (
                self.client.table("products")
                .select("*", count="exact")
                .or_(query_str)
                .order("product_name", desc=False)
                .limit(page_size)
                .offset((page - 1) * page_size)
                .execute()
                .model_dump()
            )

            # Extract the returned data and count.
            product_data = response.get("data", [])
            count = response.get("count", 0)
            if not product_data:
                return None
            products = [Product(**item) for item in product_data]
            return ProductList(
                products=products, page=page, page_size=page_size, count=count
            )

        except Exception as e:
            logger.error(f"Unexpected error searching products: {str(e)}")
            # requested range not satisfiable
            try:
                if e.code == "PGRST103":
                    return None
            except:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error searching products: {str(e)}",
            )

    async def scan_barcode(self, barcode: str) -> Optional[List[LoggedProduct]]:
        """
        Retrieve a product from the database using the provided barcode.

        Args:
            barcode (str): The barcode string used to identify the product.

        Returns:
            Product: The product object corresponding to the given barcode.
        """

        logger.info(f"Fetching product with barcode: {barcode}")

        try:
            response = (
                self.client.table("products")
                .select("*")
                .eq("barcode", barcode)
                .execute()
                .model_dump()
            )

            product_data = response.get("data", [])
            if not product_data:
                return None
            logged_products = [LoggedProduct(**item) for item in product_data]

            return logged_products

        except Exception as e:
            logger.error(
                f"Unexpected error fetching product with barcode: {barcode} : {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching product: {str(e)}",
            )

    async def update_product(
        self, barcode: str, product_data: ProductUpdate
    ) -> List[LoggedProduct]:
        """
        Updates a product record.
        Args:
            barcode (str): The ID of the product to update.
            product_data (ProductUpdate): An object containing fields to update. Fields with `None` values are ignored.

        Returns:
            LoggedProduct: The updated product data.

        Raises:
            HTTPException: If an error occurs during the update operation.
        """
        logger.info(f"Updating product with barcode:{barcode}")

        try:
            product_data = ProductUpdate.model_dump()
            clean_product_data = {
                k: v for k, v in product_data.items() if v is not None
            }
            response = (
                self.client.table("products")
                .update(**clean_product_data)
                .eq("barcode", barcode)
                .execute()
                .model_dump()
            )

            # Extract the returned data and count.
            product_data = response["data"]
            logged_products = [LoggedProduct(**item) for item in product_data]

            return logged_products

        except Exception as e:
            logger.error(f"Unexpected error updating product: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error updating product: {str(e)}",
            )

    async def upsert_product(
        self, product: Union[LoggedProduct, List[LoggedProduct]]
    ) -> Optional[List[LoggedProduct]]:
        """Upsert a product(s).

        Args:
            product: Details of the product to upsert. Could be a single product or a list of products

        Returns:
            The logged product
        """
        logger.info(f"Upsert product")

        try:
            if isinstance(product, List):
                product_dict = [p.model_dump() for p in product]
            else:
                product_dict = product.model_dump()
            response = (
                self.client.table("products")
                .upsert(product_dict)
                .execute()
                .model_dump()
            )

            logged_product_data = response["data"]
            logged_products = [LoggedProduct(**item) for item in logged_product_data]

            return logged_products

        except Exception as e:
            logger.error(f"Unexpected error logging product: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error logging product: {str(e)}",
            )

    async def delete_product(self, barcode: str) -> LoggedProduct:
        """
        Deletes a product record.
        Args:
            barcode (str): The ID of the product to delete
            product_data (ProductUpdate): An object containing fields to update. Fields with `None` values are ignored.

        Returns:
            LoggedProduct: The deleted product data.

        Raises:
            HTTPException: If an error occurs during the delete operation.
        """
        logger.info(f"Deleting product with id: {barcode}")

        try:
            response = (
                self.client.table("products").delete().eq("barcode", barcode).execute()
            )

            # Extract the returned data and count.
            product = response["data"]
            return LoggedProduct(**product)

        except Exception as e:
            logger.error(f"Unexpected error deleting product: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error deleting product: {str(e)}",
            )


product_service = ProductService()
