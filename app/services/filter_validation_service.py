"""Service for validating and normalizing search filters.


This module provides centralized validation and normalization of search filters
to ensure consistency across List and Map view endpoints.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status

from app.models.meal import SearchFilterRequest
from app.models.scan import CuisineType, DietaryRestriction

logger = logging.getLogger(__name__)


class FilterValidationService:
    """Service for validating and normalizing search filters."""
    
    @staticmethod
    def normalize_cuisine_types(cuisines: Optional[List[str]]) -> List[CuisineType]:
        """Normalize cuisine type strings to CuisineType enum.
        
        Args:
            cuisines: List of cuisine type strings (case-insensitive)
            
        Returns:
            List of normalized CuisineType enums
            
        Raises:
            HTTPException: If any cuisine type is invalid
        """
        if not cuisines:
            return []
        
        normalized = []
        invalid_cuisines = []
        
        for cuisine in cuisines:
            cuisine_lower = cuisine.lower().strip()
            try:
                # Try direct match first
                normalized_cuisine = CuisineType(cuisine_lower)
                normalized.append(normalized_cuisine)
            except ValueError:
                # Try fuzzy matching (replace spaces with underscores)
                cuisine_normalized = cuisine_lower.replace(" ", "_")
                try:
                    normalized_cuisine = CuisineType(cuisine_normalized)
                    normalized.append(normalized_cuisine)
                except ValueError:
                    invalid_cuisines.append(cuisine)
        
        if invalid_cuisines:
            valid_options = [c.value for c in CuisineType]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid cuisine type(s)",
                    "invalid_values": invalid_cuisines,
                    "valid_options": valid_options
                }
            )
        
        logger.info(f"Normalized {len(normalized)} cuisine types: {[c.value for c in normalized]}")
        return normalized
    
    @staticmethod
    def normalize_dietary_restrictions(
        restrictions: Optional[List[str]]
    ) -> List[DietaryRestriction]:
        """Normalize dietary restriction strings to DietaryRestriction enum.
        
        Args:
            restrictions: List of dietary restriction strings (case-insensitive)
            
        Returns:
            List of normalized DietaryRestriction enums
            
        Raises:
            HTTPException: If any dietary restriction is invalid
        """
        if not restrictions:
            return []
        
        normalized = []
        invalid_restrictions = []
        
        for restriction in restrictions:
            restriction_lower = restriction.lower().strip()
            try:
                # Try direct match first
                normalized_restriction = DietaryRestriction(restriction_lower)
                normalized.append(normalized_restriction)
            except ValueError:
                # Try variations (spaces to underscores, hyphens to underscores)
                restriction_normalized = (
                    restriction_lower
                    .replace(" ", "_")
                    .replace("-", "_")
                )
                try:
                    normalized_restriction = DietaryRestriction(restriction_normalized)
                    normalized.append(normalized_restriction)
                except ValueError:
                    invalid_restrictions.append(restriction)
        
        if invalid_restrictions:
            valid_options = [r.value for r in DietaryRestriction]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid dietary restriction(s)",
                    "invalid_values": invalid_restrictions,
                    "valid_options": valid_options
                }
            )
        
        logger.info(f"Normalized {len(normalized)} dietary restrictions: {[r.value for r in normalized]}")
        return normalized
    
    @staticmethod
    def parse_comma_separated(value: Optional[str]) -> List[str]:
        """Parse comma-separated string into list of trimmed strings.
        
        Args:
            value: Comma-separated string
            
        Returns:
            List of trimmed, non-empty strings
        """
        if not value:
            return []
        
        return [item.strip() for item in value.split(",") if item.strip()]
    
    @staticmethod
    def validate_search_filters(filters: SearchFilterRequest) -> SearchFilterRequest:
        """Validate and normalize all filters in a SearchFilterRequest.
        
        Args:
            filters: Search filter request to validate
            
        Returns:
            Validated and normalized SearchFilterRequest
            
        Raises:
            HTTPException: If any validation fails
        """
        # Validate location parameters
        if filters.latitude is not None and filters.longitude is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Longitude is required when latitude is provided"
            )
        
        if filters.longitude is not None and filters.latitude is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Latitude is required when longitude is provided"
            )
        
        # Validate macro targets (if any provided, all should be positive)
        if filters.calories is not None and filters.calories < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Calories cannot be negative"
            )
        
        if filters.protein is not None and filters.protein < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Protein cannot be negative"
            )
        
        if filters.carbs is not None and filters.carbs < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Carbs cannot be negative"
            )
        
        if filters.fat is not None and filters.fat < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fat cannot be negative"
            )
        
        # Validate search terms (at least one required if no location)
        if not filters.latitude and not filters.longitude:
            if not any([filters.query, filters.meal_name, filters.restaurant_name]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Either location (lat/lng) or search term (query/meal_name/restaurant_name) is required"
                )
        
        logger.info(f"Validated search filters: {filters.model_dump()}")
        return filters
    
    @staticmethod
    def build_filter_summary(filters: SearchFilterRequest) -> Dict[str, Any]:
        """Build a summary of applied filters for API response.
        
        Args:
            filters: Validated search filters
            
        Returns:
            Dictionary summarizing what filters were applied
        """
        summary = {
            "search_terms": {},
            "cuisines": [c.value for c in filters.cuisines] if filters.cuisines else [],
            "dietary_restrictions": [d.value for d in filters.dietary_restrictions] if filters.dietary_restrictions else [],
            "dietary_preference": filters.dietary_preference,
            "location": {
                "latitude": filters.latitude,
                "longitude": filters.longitude,
                "radius_km": filters.radius_km,
                "address": filters.location
            } if filters.latitude and filters.longitude else None,
            "macro_targets": {}
        }
        
        # Add search terms
        if filters.query:
            summary["search_terms"]["general"] = filters.query
        if filters.meal_name:
            summary["search_terms"]["meal"] = filters.meal_name
        if filters.restaurant_name:
            summary["search_terms"]["restaurant"] = filters.restaurant_name
        
        # Add macro targets if specified
        if filters.calories:
            summary["macro_targets"]["calories"] = filters.calories
        if filters.protein:
            summary["macro_targets"]["protein"] = filters.protein
        if filters.carbs:
            summary["macro_targets"]["carbs"] = filters.carbs
        if filters.fat:
            summary["macro_targets"]["fat"] = filters.fat
        
        # Remove empty sections
        if not summary["search_terms"]:
            del summary["search_terms"]
        if not summary["macro_targets"]:
            del summary["macro_targets"]
        
        return summary


filter_validation_service = FilterValidationService()
