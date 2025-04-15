"""Data models for meal recommendation API.

This module contains Pydantic models that define the structure of request and
response data for the meal recommendation API.
"""
from typing import Optional
from typing_extensions import Annotated
from pydantic import BaseModel, Field

class Address(BaseModel):
    """Represents a structured address returned from reverse geocoding.

    Attributes:
        country (str): Full country name.
        country_code (str): ISO country code (e.g., 'us' for United States).
        postcode (str): Postal or ZIP code.
        state (str): Name of the state or region.
        city (str): City name.
        county (str): County or district name.
        suburb (Optional[str]): Suburb or local area, if available.
        neighborhood (Optional[str]): Neighborhood within the city, if available.
        street (str): Street or road name (aliased from 'road').
        house_number (Optional[str]): House or building number, if available."""
    country: str
    country_code: str
    postcode: str
    state: str
    city: str
    county: str
    suburb: Optional[str] = None
    neighborhood: Optional[str] = None
    street: Annotated[str, Field(alias='road')]
    house_number: Optional[str] = None
    

class ReverseGeocode(BaseModel):
    """Result of a reverse geocoding operation.

    Attributes:
        display_name (str): Full display name or label for the location.
        address (Address): Structured address components for the location.
    """
    display_name: str
    address: Address




