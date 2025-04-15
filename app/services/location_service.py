import logging

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

    async def reverse_geocode(self, latitude:float, longitude:float):
        """ Retrieve geocode address from latitude and longitude

        Args:
            latitude (float): latitude coord
            longitude (float): longitude coord

        Returns:
            Dictionary with a formatted geocode name(display_name) and address
        """      
        try:
            location_data = self.locator.reverse((latitude, longitude), addressdetails=True)
            location = ReverseGeocode(**location_data.raw)
            return location
        except Exception as e:
            logger.error(f"Unexpected error getting location for longitude:{longitude} and latitude:{latitude}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error getting location: {str(e)}"
            )


location_service = LocationService()

