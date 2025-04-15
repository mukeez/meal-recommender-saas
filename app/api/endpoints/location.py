"""API endpoints for retrieving location and address information.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.api.auth_guard import auth_guard
from app.models.location import (
    ReverseGeocode
)
from app.services.location_service import location_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/reverse-geocode",
    response_model=ReverseGeocode,
    response_model_by_alias=False,
    status_code=status.HTTP_200_OK,
    summary="Get human-readable address information",
    description="Get human-readable address information from geographic coordinates (latitude and longitude)",
)
async def reverse_geocode(
        latitude: float = Query(None),
        longitude: float = Query(None),
        user=Depends(auth_guard)
) -> ReverseGeocode:
    """Get the location address.

    This endpoint retrieves human-readable address information from geographic coordinates (latitude and longitude)

    Args:
        latitude: The latitude coord
        longitude: The longitude coord
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        A response object containing a formatted address(display_name) and a dict of address information

    Raises:
        HTTPException: If there is an error processing the request
    """
    try:
        # reverse geocode latitude and longitude coords
        logger.info(f"Reverse Geocode:[latitude:{latitude}][longitude:{longitude}]")
        location = await location_service.reverse_geocode(latitude=latitude, longitude=longitude)
        return location
    
    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving location address: {str(e)}"
        )


