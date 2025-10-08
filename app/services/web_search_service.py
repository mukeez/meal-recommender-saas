"""Web search service for product information lookup.

This module provides functions to search the web for product information
when barcode scanning fails to find results in local database or OpenFoodFacts.
"""

import logging
import httpx
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class WebSearchService:
    """Service for web searching product information."""
    
    def __init__(self):
        """Initialize the web search service."""
        self.search_api_url = "https://api.search.emit-labs.com"
        # You'll need to add this to your settings
        self.api_key = getattr(settings, 'SEARCH_API_KEY', None)
    
    async def search_product_by_barcode(self, barcode: str) -> Optional[List[Dict[str, Any]]]:
        """Search for product information by barcode using web search.
        
        Args:
            barcode: The product barcode to search for
            
        Returns:
            List of search results or None if no results found
            
        Raises:
            HTTPException: If the search API fails
        """
        try:
            if not self.api_key:
                logger.warning("Search API key not configured, skipping web search")
                return None
            
            # Create search query for barcode
            search_query = f"product barcode {barcode} nutrition facts ingredients"
            
            logger.info(f"Searching web for barcode: {barcode}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.search_api_url}/api/v1/search",
                    params={
                        "q": search_query,
                        "limit": 3,
                        "categories": "general",
                        "language": "en",
                        "safesearch": 1
                    },
                    headers={
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    search_data = response.json()
                    results = search_data.get("results", [])
                    
                    if results:
                        logger.info(f"Found {len(results)} web search results for barcode: {barcode}")
                        return results
                    else:
                        logger.info(f"No web search results found for barcode: {barcode}")
                        return None
                else:
                    logger.error(f"Search API error: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            logger.warning(f"Web search timed out for barcode: {barcode}")
            return None
        except Exception as e:
            logger.error(f"Error during web search for barcode {barcode}: {str(e)}")
            return None


web_search_service = WebSearchService()