"""Google Places API service for restaurant data.


This module provides functions to interact with Google Places API
to fetch nearby restaurants and place details.
"""

import logging
import httpx
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class GooglePlacesAPIError(Exception):
    """Custom exception for Google Places API errors."""
    pass


class GooglePlacesService:
    """Service for interacting with Google Places API."""
    
    def __init__(self):
        """Initialize the Google Places service."""
        self.api_key = settings.GOOGLE_PLACES_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api/place"
    
    def _build_search_keyword(
        self,
        query: Optional[str] = None,
        meal_name: Optional[str] = None,
        restaurant_name: Optional[str] = None,
        cuisines: Optional[List[str]] = None
    ) -> Optional[str]:
        """Build search keyword from filter parameters.
        
        Priority:
        1. restaurant_name (most specific)
        2. query (general search)
        3. meal_name + cuisines (combined)
        
        Args:
            query: General search term
            meal_name: Specific meal name
            restaurant_name: Specific restaurant name
            cuisines: List of cuisine types
            
        Returns:
            Combined search keyword or None
        """
        # Priority 1: Restaurant name search
        if restaurant_name:
            logger.info(f"Using restaurant name as keyword: {restaurant_name}")
            return restaurant_name
        
        # Priority 2: General query
        if query:
            logger.info(f"Using general query as keyword: {query}")
            return query
        
        # Priority 3: Meal name with cuisines
        keywords = []
        if meal_name:
            keywords.append(meal_name)
        
        if cuisines:
            # Add cuisine types to search
            cuisine_terms = [c.replace("_", " ") for c in cuisines]
            keywords.extend(cuisine_terms)
        
        if keywords:
            combined = " ".join(keywords)
            logger.info(f"Built combined keyword: {combined}")
            return combined
        
        return None
    
    def _filter_by_cuisine(
        self,
        places: List[Dict[str, Any]],
        cuisines: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Filter places by cuisine types.
        
        Args:
            places: List of place results from API
            cuisines: List of cuisine types to filter by (e.g., ['italian', 'mexican'])
            
        Returns:
            Filtered list of places matching cuisine criteria
        """
        if not cuisines:
            return places
        
        # Normalize cuisine types for matching
        cuisine_keywords = set()
        for cuisine in cuisines:
            cuisine_keywords.add(cuisine.lower())
            cuisine_keywords.add(f"{cuisine}_restaurant".lower())
        
        filtered = []
        for place in places:
            place_types = place.get("types", [])
            place_types_lower = [t.lower() for t in place_types]
            
            # Check if any place type matches our cuisine filters
            if any(cuisine in place_types_lower for cuisine in cuisine_keywords):
                filtered.append(place)
        
        logger.info(f"Filtered {len(places)} places to {len(filtered)} matching cuisines: {cuisines}")
        return filtered
        
    async def nearby_search(
        self,
        latitude: float,
        longitude: float,
        radius: int = 5000,  # meters
        keyword: Optional[str] = None,
        place_type: str = "restaurant"
    ) -> List[Dict[str, Any]]:
        """Search for nearby restaurants using Google Places API.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            radius: Search radius in meters (max 50000)
            keyword: Optional search keyword
            place_type: Type of place to search for
            
        Returns:
            List of place results from Google Places
            
        Raises:
            GooglePlacesAPIError: If API call fails
        """
        if not self.api_key:
            logger.error("Google Places API key not configured")
            raise GooglePlacesAPIError("Google Places API not configured")
            
        try:
            url = f"{self.base_url}/nearbysearch/json"
            
            params = {
                "location": f"{latitude},{longitude}",
                "radius": min(radius, 50000),  # Max 50km
                "type": place_type,
                "key": self.api_key
            }
            
            if keyword:
                params["keyword"] = keyword
            
            logger.info(f"Google Places Nearby Search: lat={latitude}, lng={longitude}, radius={radius}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                
                if response.status_code != 200:
                    logger.error(f"Google Places API error: {response.status_code} - {response.text}")
                    raise GooglePlacesAPIError(f"API returned status {response.status_code}")
                
                data = response.json()
                
                if data.get("status") not in ["OK", "ZERO_RESULTS"]:
                    logger.error(f"Google Places API status: {data.get('status')}")
                    raise GooglePlacesAPIError(f"API status: {data.get('status')}")
                
                results = data.get("results", [])
                logger.info(f"Found {len(results)} restaurants from Google Places")
                
                return results
                
        except httpx.TimeoutException:
            logger.error("Google Places API timeout")
            raise GooglePlacesAPIError("Request timed out")
        except httpx.RequestError as e:
            logger.error(f"Google Places API request error: {e}")
            raise GooglePlacesAPIError(f"Request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in Google Places nearby search: {e}")
            raise GooglePlacesAPIError(f"Unexpected error: {str(e)}")
    
    async def get_place_details(
        self,
        place_id: str,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get detailed information about a place.
        
        Args:
            place_id: Google Places ID
            fields: List of fields to retrieve (if None, gets all basic fields)
            
        Returns:
            Place details dictionary
            
        Raises:
            GooglePlacesAPIError: If API call fails
        """
        if not self.api_key:
            raise GooglePlacesAPIError("Google Places API not configured")
        
        if fields is None:
            # Default fields for restaurant details
            fields = [
                "place_id",
                "name",
                "formatted_address",
                "geometry",
                "rating",
                "price_level",
                "types",
                "website",
                "formatted_phone_number",
                "opening_hours",
                "photos"
            ]
        
        try:
            url = f"{self.base_url}/details/json"
            
            params = {
                "place_id": place_id,
                "fields": ",".join(fields),
                "key": self.api_key
            }
            
            logger.info(f"Getting place details for: {place_id}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                
                if response.status_code != 200:
                    logger.error(f"Google Places API error: {response.status_code}")
                    raise GooglePlacesAPIError(f"API returned status {response.status_code}")
                
                data = response.json()
                
                if data.get("status") != "OK":
                    logger.error(f"Google Places API status: {data.get('status')}")
                    raise GooglePlacesAPIError(f"API status: {data.get('status')}")
                
                result = data.get("result", {})
                logger.info(f"Got details for: {result.get('name', 'unknown')}")
                
                return result
                
        except httpx.TimeoutException:
            logger.error("Google Places API timeout")
            raise GooglePlacesAPIError("Request timed out")
        except httpx.RequestError as e:
            logger.error(f"Google Places API request error: {e}")
            raise GooglePlacesAPIError(f"Request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in place details: {e}")
            raise GooglePlacesAPIError(f"Unexpected error: {str(e)}")
    
    def extract_menu_url(self, place_details: Dict[str, Any]) -> Optional[str]:
        """Extract menu URL from place details.
        
        Google Places doesn't provide direct menu URLs, but we can check:
        1. The website field (some restaurants have menu pages)
        2. Look for common menu URL patterns
        
        Args:
            place_details: Place details from API
            
        Returns:
            Menu URL if found, None otherwise
        """
        website = place_details.get("website")
        
        if not website:
            return None
        
        # If website contains common menu keywords, it might be a menu URL
        menu_keywords = ["menu", "order", "food"]
        website_lower = website.lower()
        
        if any(keyword in website_lower for keyword in menu_keywords):
            logger.info(f"Found potential menu URL: {website}")
            return website
        
        # Otherwise, return the website as it might have menu info
        return website
    
    async def nearby_search_with_filters(
        self,
        latitude: float,
        longitude: float,
        radius: int,
        query: Optional[str] = None,
        meal_name: Optional[str] = None,
        restaurant_name: Optional[str] = None,
        cuisines: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search for nearby restaurants with unified filter support.
        
        This method combines search keyword building and cuisine filtering
        to provide consistent search results across List and Map views.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            radius: Search radius in meters
            query: General search term
            meal_name: Specific meal name to search for
            restaurant_name: Specific restaurant name to search for
            cuisines: List of cuisine types to filter by
            
        Returns:
            Filtered list of place results
            
        Raises:
            GooglePlacesAPIError: If API call fails
        """
        # Build search keyword from filters
        keyword = self._build_search_keyword(
            query=query,
            meal_name=meal_name,
            restaurant_name=restaurant_name,
            cuisines=cuisines
        )
        
        # Perform nearby search
        places = await self.nearby_search(
            latitude=latitude,
            longitude=longitude,
            radius=radius,
            keyword=keyword,
            place_type="restaurant"
        )
        
        # Post-filter by cuisine if specified
        if cuisines:
            places = self._filter_by_cuisine(places, cuisines)
        
        return places
    
    def get_photo_url(
        self,
        photo_reference: str,
        max_width: int = 400
    ) -> str:
        """Generate URL for a Google Places photo.
        
        Args:
            photo_reference: Photo reference from API
            max_width: Maximum width of photo
            
        Returns:
            URL to fetch the photo
        """
        return (
            f"{self.base_url}/photo"
            f"?maxwidth={max_width}"
            f"&photo_reference={photo_reference}"
            f"&key={self.api_key}"
        )


google_places_service = GooglePlacesService()
