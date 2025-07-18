from typing import List, Dict, Any, Optional
import logging
from app.services.base_database_service import BaseDatabaseService
from app.services.location_service import location_service
from app.tasks.scraping_tasks import scrape_restaurants_task


logger = logging.getLogger(__name__)

class RestaurantServiceError(Exception):
    """Custom exception for restaurant service errors."""
    pass

class RestaurantService:
    """
    Handles restaurant-related operations, such as retrieving restaurants within a 
    specified radius using spatial queries. Ensures a database service implementation 
    is available.
    """
    def __init__(self):
        """
        Initializes the RestaurantService and checks for available database service implementations.
        Raises:
            RestaurantServiceError: If no database service implementation is available.
        """
        # Ensure at least one database service implementation is available
        if not BaseDatabaseService.subclasses:
                raise RestaurantServiceError("No database service implementation available")


    
    def get_restaurants_within_radius(
        self,
        latitude: float, 
        longitude: float, 
        radius_km: float = 0.1,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find restaurants within the specified radius.
        
        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            radius_km: Search radius in kilometers
            limit: Maximum number of results to return
            
        Returns:
            List of restaurant data dictionaries
        """
        try:
            response = BaseDatabaseService.subclasses[0]().rpc(
            "find_restaurants_within_radius", 
            {
                "lat": latitude,
                "lng": longitude,
                "radius_meters": radius_km * 1000,
                "result_limit": limit
            }
        )
            if not response:
                return []
            return response
            
        except Exception as e:
            logger.error(f"Error finding restaurants within radius: {e}")
            return []
        
    
    async def find_restaurants_for_location(
        self, location:str, latitude: float, longitude: float, search_radius: Optional[float] = None
    ) -> List[Dict]:
        """
        Find restaurants for a given location by geocoding the address and searching within a radius.
        Args:
            location (str): The address or location name to search for.
            search_radius (Optional[float]): The search radius in kilometers. If None, will be determined automatically.
        Returns:
            List[Dict]: A list of restaurant data dictionaries within the specified radius.
        Raises:
            RestaurantServiceError: If no database service implementation is available.
        """
        try:

            logger.info(f"Geocoded location '{location}' to lat: {latitude}, lon: {longitude}")

            location_data = await location_service.reverse_geocode(
                latitude=latitude, 
                longitude=longitude
            )

            logger.info(f"Reverse geocoded location data: {location_data}")

            if search_radius is None:
                search_radius = await location_service.determine_search_radius(location_data=location_data)


            restaurants = self.get_restaurants_within_radius(
                latitude, longitude, search_radius)
            logger.info(f"Found {len(restaurants)} restaurants for location '{location}'")

            if not restaurants:
                # Launch background task for scraping
                scrape_restaurants_task.delay(
                    location_name=location,
                    latitude=latitude,
                    longitude=longitude
                )

            return restaurants if restaurants else []
        except Exception as e:
            logger.error(f"Error finding restaurants for location: {e}")
            return []

    


restaurant_service = RestaurantService()