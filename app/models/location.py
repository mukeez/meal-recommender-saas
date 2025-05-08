"""Data models for the location API.

This module contains Pydantic models that define the structure of request and
response data for the location API.
"""

from typing import Optional
from typing_extensions import Annotated
from pydantic import BaseModel, Field, ConfigDict


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

    country: Annotated[str, Field(..., description="Full country name")]
    country_code: Annotated[
        str, Field(..., description="ISO country code (e.g., 'us' for United States)")
    ]
    postcode: Annotated[Optional[str], Field(None, description="Full country name")]
    state: Annotated[str, Field(..., description="Full country name")]
    city: Annotated[str, Field(..., description="City name")]
    county: Annotated[str, Field(..., description="County or district name")]
    suburb: Annotated[Optional[str], Field(None, description="Suburb or local area")]
    neighborhood: Annotated[
        Optional[str],
        Field(None, description="Neighborhood within the city, if available"),
    ]
    street: Annotated[
        str,
        Field(
            ...,
            alias="road",
            description="Street or road name (aliased from 'road' provided by geopy)",
        ),
    ]
    house_number: Annotated[
        Optional[str], Field(None, description="House or building number, if available")
    ]

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)



class ReverseGeocode(BaseModel):
    """Result of a reverse geocoding operation.

    Attributes:
        display_name (str): Full display name or label for the location.
        address (Address): Structured address components for the location.
    """

    display_name: Annotated[
        str, Field(..., description="Full display name or label for the location")
    ]
    address: Address
