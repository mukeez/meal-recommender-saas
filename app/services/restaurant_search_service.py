"""Unified restaurant search service for consistent filtering across List and Map views.


This service orchestrates Google Places API searches and meal matching to ensure
that the same search filters produce the same restaurant results in both
List view (meal suggestions) and Map view (restaurant pins).
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone

from app.models.meal import SearchFilterRequest
from app.models.scan import CuisineType, DietaryRestriction
from app.services.google_places_service import google_places_service, GooglePlacesAPIError
from app.services.restaurant_meal_matching_service import restaurant_meal_matching_service
from app.services.cache_service import cache_service
from app.services.filter_validation_service import filter_validation_service

logger = logging.getLogger(__name__)


class RestaurantSearchService:
    """Unified service for searching restaurants with consistent filtering."""
    
    def __init__(self):
        self.google_places = google_places_service
        self.meal_matcher = restaurant_meal_matching_service
        self.cache = cache_service
        self.filter_validator = filter_validation_service
    
    async def search_restaurants(
        self,
        filters: SearchFilterRequest,
        user_id: Optional[str] = None,
        view_type: str = "list"
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Search for restaurants using unified filters.
        
        This method ensures that the same filters produce the same restaurant
        subset in both List and Map views by:
        1. Building a unified cache key from all filter parameters
        2. Using the same Google Places search parameters
        3. Applying the same post-filtering logic
        
        Args:
            filters: Validated search filter request
            user_id: Optional user ID for per-user caching
            view_type: "list" or "map" for differentiated caching
            
        Returns:
            Tuple of (list of restaurant data, is_cached boolean)
            
        Raises:
            GooglePlacesAPIError: If Google Places API call fails
        """
        # Validate filters
        validated_filters = self.filter_validator.validate_search_filters(filters)
        
        # Check cache first
        cache_key = self.cache.generate_unified_cache_key(
            latitude=validated_filters.latitude,
            longitude=validated_filters.longitude,
            radius=validated_filters.radius_km,
            query=validated_filters.query,
            meal_name=validated_filters.meal_name,
            restaurant_name=validated_filters.restaurant_name,
            cuisines=[c.value for c in validated_filters.cuisines] if validated_filters.cuisines else None,
            dietary_restrictions=[d.value for d in validated_filters.dietary_restrictions] if validated_filters.dietary_restrictions else None,
            dietary_preference=validated_filters.dietary_preference,
            user_id=user_id,
            view_type=view_type
        )
        
        # Try to get from cache
        cached_data = await self.cache.get_cached_map_pins(cache_key)
        if cached_data:
            logger.info(f"Cache HIT for {view_type} view: {cache_key}")
            return cached_data.get("restaurants", []), True
        
        logger.info(f"Cache MISS for {view_type} view: {cache_key}")
        
        # Search Google Places with unified filters
        places = await self._search_google_places(validated_filters)
        
        # Get detailed information for each place
        restaurants = await self._enrich_restaurant_data(places, validated_filters)
        
        # Cache the results
        cache_data = {
            "restaurants": restaurants,
            "filters_applied": self.filter_validator.build_filter_summary(validated_filters),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_count": len(restaurants)
        }
        
        await self.cache.set_cached_map_pins(cache_key, cache_data, ttl=3600)  # 1 hour TTL
        
        return restaurants, False
    
    async def _search_google_places(
        self,
        filters: SearchFilterRequest
    ) -> List[Dict[str, Any]]:
        """Search Google Places API with unified filters.
        
        Args:
            filters: Validated search filters
            
        Returns:
            List of place results from Google Places API
        """
        if not filters.latitude or not filters.longitude:
            raise ValueError("Latitude and longitude are required for restaurant search")
        
        # Convert radius from km to meters
        radius_meters = int(filters.radius_km * 1000)
        
        # Extract cuisine values for filtering
        cuisine_values = [c.value for c in filters.cuisines] if filters.cuisines else None
        
        logger.info(
            f"Searching Google Places: "
            f"lat={filters.latitude}, lng={filters.longitude}, "
            f"radius={radius_meters}m, cuisines={cuisine_values}"
        )
        
        # Use the unified search method from Google Places service
        places = await self.google_places.nearby_search_with_filters(
            latitude=filters.latitude,
            longitude=filters.longitude,
            radius=radius_meters,
            query=filters.query,
            meal_name=filters.meal_name,
            restaurant_name=filters.restaurant_name,
            cuisines=cuisine_values
        )
        
        logger.info(f"Found {len(places)} restaurants from Google Places")
        return places
    
    async def _enrich_restaurant_data(
        self,
        places: List[Dict[str, Any]],
        filters: SearchFilterRequest
    ) -> List[Dict[str, Any]]:
        """Enrich place data with additional details and meal recommendations.
        
        Args:
            places: List of places from Google Places API
            filters: Search filters (for meal matching)
            
        Returns:
            List of enriched restaurant data
        """
        enriched_restaurants = []
        
        for place in places[:filters.limit]:  # Respect limit
            try:
                # Get place details
                place_id = place.get("place_id")
                if not place_id:
                    logger.warning(f"Skipping place without place_id: {place.get('name')}")
                    continue
                
                details = await self.google_places.get_place_details(place_id)
                
                # Extract basic info
                restaurant_data = {
                    "id": place_id,
                    "google_place_id": place_id,
                    "name": details.get("name", "Unknown"),
                    "latitude": details.get("geometry", {}).get("location", {}).get("lat"),
                    "longitude": details.get("geometry", {}).get("location", {}).get("lng"),
                    "address": details.get("formatted_address"),
                    "rating": details.get("rating"),
                    "price_level": details.get("price_level"),
                    "cuisine_types": self._extract_cuisine_types(details.get("types", [])),
                    "photo_url": self._get_first_photo_url(details.get("photos")),
                    "menu_url": self.google_places.extract_menu_url(details),
                    "phone_number": details.get("formatted_phone_number"),
                    "website": details.get("website"),
                    "opening_hours": details.get("opening_hours", {}).get("weekday_text"),
                    "distance_km": self._calculate_distance(
                        filters.latitude,
                        filters.longitude,
                        details.get("geometry", {}).get("location", {}).get("lat"),
                        details.get("geometry", {}).get("location", {}).get("lng")
                    )
                }
                
                enriched_restaurants.append(restaurant_data)
                
            except Exception as e:
                logger.error(f"Error enriching restaurant data for {place.get('name')}: {e}")
                continue
        
        return enriched_restaurants
    
    def _extract_cuisine_types(self, place_types: List[str]) -> List[str]:
        """Extract cuisine types from Google Places types.
        
        Args:
            place_types: List of place types from Google
            
        Returns:
            List of human-readable cuisine types
        """
        cuisine_types = []
        
        for place_type in place_types:
            if "_restaurant" in place_type:
                # Extract cuisine: "italian_restaurant" -> "Italian"
                cuisine = place_type.replace("_restaurant", "").replace("_", " ").title()
                cuisine_types.append(cuisine)
        
        if not cuisine_types:
            cuisine_types.append("Restaurant")
        
        return cuisine_types
    
    def _get_first_photo_url(self, photos: Optional[List[Dict[str, Any]]]) -> Optional[str]:
        """Get URL for first photo.
        
        Args:
            photos: List of photo references from Google Places
            
        Returns:
            Photo URL or None
        """
        if not photos or len(photos) == 0:
            return None
        
        first_photo_ref = photos[0].get("photo_reference")
        if not first_photo_ref:
            return None
        
        return self.google_places.get_photo_url(first_photo_ref, max_width=400)
    
    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: Optional[float],
        lon2: Optional[float]
    ) -> Optional[float]:
        """Calculate distance between two coordinates in kilometers.
        
        Uses the Haversine formula for great-circle distance.
        
        Args:
            lat1: Starting latitude
            lon1: Starting longitude
            lat2: Ending latitude
            lon2: Ending longitude
            
        Returns:
            Distance in kilometers or None if coordinates are invalid
        """
        if lat2 is None or lon2 is None:
            return None
        
        from math import radians, sin, cos, sqrt, atan2
        
        # Earth's radius in kilometers
        R = 6371.0
        
        # Convert to radians
        lat1_rad = radians(lat1)
        lon1_rad = radians(lon1)
        lat2_rad = radians(lat2)
        lon2_rad = radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        
        distance = R * c
        
        return round(distance, 2)
    
    async def search_with_meal_recommendations(
        self,
        filters: SearchFilterRequest,
        user_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Search restaurants and generate meal recommendations for each.
        
        This method is used by the List view to get restaurants with
        their top meal recommendations.
        
        Args:
            filters: Validated search filters
            user_id: Optional user ID for tracking
            
        Returns:
            Tuple of (list of restaurants with meals, is_cached boolean)
        """
        # Get base restaurant data
        restaurants, is_cached = await self.search_restaurants(
            filters=filters,
            user_id=user_id,
            view_type="list"
        )
        
        # Generate meal recommendations for each restaurant
        for restaurant in restaurants:
            try:
                # Build user preferences
                user_preferences = {
                    "dietary_restrictions": [d.value for d in filters.dietary_restrictions] if filters.dietary_restrictions else [],
                    "dietary_preference": filters.dietary_preference,
                    "user_id": user_id
                }
                
                # Build macro targets if specified
                macro_targets = None
                if filters.calories or filters.protein or filters.carbs or filters.fat:
                    macro_targets = {
                        "calories": filters.calories,
                        "protein": filters.protein,
                        "carbs": filters.carbs,
                        "fat": filters.fat
                    }
                
                # Prepare restaurant data for meal matching
                restaurant_data = {
                    "name": restaurant["name"],
                    "place_types": [c.lower() + "_restaurant" for c in restaurant.get("cuisine_types", [])]
                }
                
                # Generate top meal for this restaurant
                meal = await self.meal_matcher.get_top_meal_for_restaurant(
                    restaurant=restaurant_data,
                    user_preferences=user_preferences,
                    macro_targets=macro_targets
                )
                
                # Filter by meal name if specified
                if filters.meal_name:
                    if self.meal_matcher.filter_by_meal_name(meal, filters.meal_name):
                        restaurant["meals"] = [meal]
                        restaurant["top_meal"] = meal
                    else:
                        restaurant["meals"] = []
                        restaurant["top_meal"] = None
                else:
                    restaurant["meals"] = [meal]
                    restaurant["top_meal"] = meal
                
            except Exception as e:
                logger.error(f"Error generating meals for {restaurant['name']}: {e}")
                restaurant["meals"] = []
                restaurant["top_meal"] = None
        
        return restaurants, is_cached


# Singleton instance
restaurant_search_service = RestaurantSearchService()
