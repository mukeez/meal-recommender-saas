import logging
from typing import Optional, Tuple

from fastapi import HTTPException, status
from geopy.geocoders import Nominatim
from app.models.location import ReverseGeocode


logger = logging.getLogger(__name__)


class LocationService:
    """Service for performing reverse geocoding using the Nominatim geocoder.

    This class provides an asynchronous method to retrieve human-readable
    address information from geographic coordinates (latitude and longitude).
    """

    def __init__(self):
        """Initialize geocoder."""
        self.locator = Nominatim(user_agent="mealapi")

    async def reverse_geocode(self, latitude: float, longitude: float):
        """Retrieve geocode address from latitude and longitude

        Args:
            latitude (float): latitude coord
            longitude (float): longitude coord

        Returns:
            Dictionary with a formatted geocode name(display_name) and address
        """
        try:
            location_data = self.locator.reverse(
                (latitude, longitude), addressdetails=True
            )
            location = ReverseGeocode(**location_data.raw)
            return location
        except Exception as e:
            logger.error(
                f"Unexpected error getting location for longitude:{longitude} and latitude:{latitude}: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error getting location: {str(e)}",
            )

    async def determine_search_radius(
        self,
        location_data: Optional[ReverseGeocode] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> float:
        """
        Determine appropriate search radius based on detailed Nominatim location data.

        Args:
            location_data: Optional geocoded location data
            latitude: Optional latitude for geocoding
            longitude: Optional longitude for geocoding

        Returns:
            float: Search radius in kilometers
        """
        # Get location data if not provided
        if not location_data and latitude and longitude:
            try:
                location_data = await self.reverse_geocode(latitude, longitude)
            except Exception as e:
                logger.warning(f"Could not get location data: {e}")
                return 2.0  # Default radius if geocoding fails

        if not location_data:
            return 2.0  # Default radius

        # Extract address components and metadata
        address = location_data.address.model_dump()
        location_type = location_data.type
        importance = float(location_data.importance)
        class_type = location_data.location_class

        # Major urban centers - dense areas
        if (address.get("city") and importance > 0.7) or location_type == "city":
            if address.get("suburb") or address.get("neighbourhood") or address.get(
                "quarter"
            ):
                # Downtown/central districts
                return 0.8
            return 1.0

        # Smaller cities or suburban areas
        if address.get("city") or location_type in ["town", "suburb"]:
            return 1.5

        # Medium density areas
        if address.get("suburb") or address.get("neighbourhood") or location_type in [
            "village",
            "hamlet",
        ]:
            return 2.0

        # Less dense areas
        if address.get("town") or address.get("village"):
            return 2.5

        # Consider amenities or POIs
        if class_type in ["amenity", "shop", "leisure"]:
            # Areas with businesses/amenities tend to be more built-up
            return 1.5

        # Consider postcode presence (usually indicates some development)
        if address.get("postcode"):
            return 2.5

        # Rural or undefined areas
        return 3.0

    def geocode_address(self, address: str) -> Tuple[Optional[float], Optional[float]]:
        """Convert address to geographic coordinates

        Args:
            address (str): Address or location name to geocode

        Returns:
            Tuple[Optional[float], Optional[float]]: (latitude, longitude) tuple or (None, None) if geocoding fails
        """
        try:
            if not address or not address.strip():
                return None, None
                
            location = self.locator.geocode(
                address, 
                exactly_one=True,
                addressdetails=True
            )
            
            if location:
                return location.latitude, location.longitude
            return None, None
            
        except Exception as e:
            logger.error(f"Error geocoding address '{address}': {str(e)}")
            return None, None


location_service = LocationService()
