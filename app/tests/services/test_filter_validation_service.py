"""Unit tests for filter validation service."""

import pytest
from fastapi import HTTPException
from app.services.filter_validation_service import filter_validation_service
from app.models.meal import SearchFilterRequest
from app.models.scan import CuisineType, DietaryRestriction


class TestNormalizeCuisineTypes:
    """Test cuisine type normalization."""
    
    def test_normalize_valid_cuisines(self):
        """Test normalization of valid cuisine types."""
        cuisines = ["italian", "chinese", "mexican"]
        result = filter_validation_service.normalize_cuisine_types(cuisines)
        
        assert len(result) == 3
        assert CuisineType.ITALIAN in result
        assert CuisineType.CHINESE in result
        assert CuisineType.MEXICAN in result
    
    def test_normalize_case_insensitive(self):
        """Test that normalization is case-insensitive."""
        cuisines = ["ITALIAN", "Chinese", "MeXiCaN"]
        result = filter_validation_service.normalize_cuisine_types(cuisines)
        
        assert len(result) == 3
        assert CuisineType.ITALIAN in result
        assert CuisineType.CHINESE in result
        assert CuisineType.MEXICAN in result
    
    def test_normalize_with_spaces(self):
        """Test normalization of cuisines with spaces."""
        cuisines = ["middle eastern", "middle_eastern"]
        result = filter_validation_service.normalize_cuisine_types(cuisines)
        
        assert len(result) == 2
        assert all(c == CuisineType.MIDDLE_EASTERN for c in result)
    
    def test_normalize_empty_list(self):
        """Test normalization of empty list."""
        result = filter_validation_service.normalize_cuisine_types([])
        assert result == []
    
    def test_normalize_none(self):
        """Test normalization of None."""
        result = filter_validation_service.normalize_cuisine_types(None)
        assert result == []
    
    def test_normalize_invalid_cuisine(self):
        """Test that invalid cuisine types raise HTTPException."""
        cuisines = ["italian", "invalid_cuisine", "chinese"]
        
        with pytest.raises(HTTPException) as exc_info:
            filter_validation_service.normalize_cuisine_types(cuisines)
        
        assert exc_info.value.status_code == 400
        assert "invalid_cuisine" in str(exc_info.value.detail["invalid_values"])
        assert "valid_options" in exc_info.value.detail


class TestNormalizeDietaryRestrictions:
    """Test dietary restriction normalization."""
    
    def test_normalize_valid_restrictions(self):
        """Test normalization of valid dietary restrictions."""
        restrictions = ["vegan", "gluten_free", "halal"]
        result = filter_validation_service.normalize_dietary_restrictions(restrictions)
        
        assert len(result) == 3
        assert DietaryRestriction.VEGAN in result
        assert DietaryRestriction.GLUTEN_FREE in result
        assert DietaryRestriction.HALAL in result
    
    def test_normalize_case_insensitive(self):
        """Test that normalization is case-insensitive."""
        restrictions = ["VEGAN", "Gluten_Free", "HaLaL"]
        result = filter_validation_service.normalize_dietary_restrictions(restrictions)
        
        assert len(result) == 3
        assert DietaryRestriction.VEGAN in result
        assert DietaryRestriction.GLUTEN_FREE in result
        assert DietaryRestriction.HALAL in result
    
    def test_normalize_with_hyphens_and_spaces(self):
        """Test normalization with hyphens and spaces."""
        restrictions = ["gluten-free", "gluten free", "gluten_free"]
        result = filter_validation_service.normalize_dietary_restrictions(restrictions)
        
        assert len(result) == 3
        assert all(r == DietaryRestriction.GLUTEN_FREE for r in result)
    
    def test_normalize_empty_list(self):
        """Test normalization of empty list."""
        result = filter_validation_service.normalize_dietary_restrictions([])
        assert result == []
    
    def test_normalize_none(self):
        """Test normalization of None."""
        result = filter_validation_service.normalize_dietary_restrictions(None)
        assert result == []
    
    def test_normalize_invalid_restriction(self):
        """Test that invalid restrictions raise HTTPException."""
        restrictions = ["vegan", "invalid_restriction", "halal"]
        
        with pytest.raises(HTTPException) as exc_info:
            filter_validation_service.normalize_dietary_restrictions(restrictions)
        
        assert exc_info.value.status_code == 400
        assert "invalid_restriction" in str(exc_info.value.detail["invalid_values"])
        assert "valid_options" in exc_info.value.detail


class TestParseCommaSeparated:
    """Test comma-separated string parsing."""
    
    def test_parse_simple_string(self):
        """Test parsing simple comma-separated string."""
        result = filter_validation_service.parse_comma_separated("italian,chinese,mexican")
        assert result == ["italian", "chinese", "mexican"]
    
    def test_parse_with_spaces(self):
        """Test parsing with extra spaces."""
        result = filter_validation_service.parse_comma_separated("italian , chinese , mexican")
        assert result == ["italian", "chinese", "mexican"]
    
    def test_parse_with_trailing_comma(self):
        """Test parsing with trailing comma."""
        result = filter_validation_service.parse_comma_separated("italian,chinese,")
        assert result == ["italian", "chinese"]
    
    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = filter_validation_service.parse_comma_separated("")
        assert result == []
    
    def test_parse_none(self):
        """Test parsing None."""
        result = filter_validation_service.parse_comma_separated(None)
        assert result == []


class TestValidateSearchFilters:
    """Test search filter validation."""
    
    def test_validate_valid_filters_with_location(self):
        """Test validation of valid filters with location."""
        filters = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278,
            radius_km=5.0,
            query="pizza",
            cuisines=[CuisineType.ITALIAN],
            dietary_restrictions=[DietaryRestriction.VEGAN]
        )
        
        result = filter_validation_service.validate_search_filters(filters)
        assert result == filters
    
    def test_validate_valid_filters_without_location(self):
        """Test validation of valid filters without location."""
        filters = SearchFilterRequest(
            query="pizza",
            cuisines=[CuisineType.ITALIAN]
        )
        
        result = filter_validation_service.validate_search_filters(filters)
        assert result == filters
    
    def test_validate_latitude_without_longitude(self):
        """Test that latitude without longitude raises error."""
        filters = SearchFilterRequest(
            latitude=51.5074,
            query="pizza"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            filter_validation_service.validate_search_filters(filters)
        
        assert exc_info.value.status_code == 400
        assert "Longitude is required" in exc_info.value.detail
    
    def test_validate_longitude_without_latitude(self):
        """Test that longitude without latitude raises error."""
        filters = SearchFilterRequest(
            longitude=-0.1278,
            query="pizza"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            filter_validation_service.validate_search_filters(filters)
        
        assert exc_info.value.status_code == 400
        assert "Latitude is required" in exc_info.value.detail
    
    def test_validate_negative_calories(self):
        """Test that negative calories raise validation error from Pydantic."""
        with pytest.raises(Exception) as exc_info:
            filters = SearchFilterRequest(
                latitude=51.5074,
                longitude=-0.1278,
                calories=-100
            )
        
        # Pydantic validates this at model instantiation
        assert "greater_than_equal" in str(exc_info.value) or "Calories cannot be negative" in str(exc_info.value)
    
    def test_validate_negative_protein(self):
        """Test that negative protein raises validation error from Pydantic."""
        with pytest.raises(Exception) as exc_info:
            filters = SearchFilterRequest(
                latitude=51.5074,
                longitude=-0.1278,
                protein=-50
            )
        
        # Pydantic validates this at model instantiation
        assert "greater_than_equal" in str(exc_info.value) or "Protein cannot be negative" in str(exc_info.value)
    
    def test_validate_no_location_no_search_term(self):
        """Test that missing both location and search term raises error."""
        filters = SearchFilterRequest(
            cuisines=[CuisineType.ITALIAN]
        )
        
        with pytest.raises(HTTPException) as exc_info:
            filter_validation_service.validate_search_filters(filters)
        
        assert exc_info.value.status_code == 400
        assert "location" in exc_info.value.detail.lower()
        assert "search term" in exc_info.value.detail.lower()


class TestBuildFilterSummary:
    """Test filter summary building."""
    
    def test_build_summary_with_all_filters(self):
        """Test building summary with all filter types."""
        filters = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278,
            radius_km=5.0,
            query="pizza",
            meal_name="margherita",
            restaurant_name="bella italia",
            cuisines=[CuisineType.ITALIAN, CuisineType.MEXICAN],
            dietary_restrictions=[DietaryRestriction.VEGAN, DietaryRestriction.GLUTEN_FREE],
            dietary_preference="vegetarian",
            calories=600,
            protein=30,
            carbs=70,
            fat=15
        )
        
        summary = filter_validation_service.build_filter_summary(filters)
        
        assert "search_terms" in summary
        assert summary["search_terms"]["general"] == "pizza"
        assert summary["search_terms"]["meal"] == "margherita"
        assert summary["search_terms"]["restaurant"] == "bella italia"
        
        assert "cuisines" in summary
        assert "italian" in summary["cuisines"]
        assert "mexican" in summary["cuisines"]
        
        assert "dietary_restrictions" in summary
        assert "vegan" in summary["dietary_restrictions"]
        assert "gluten_free" in summary["dietary_restrictions"]
        
        assert summary["dietary_preference"] == "vegetarian"
        
        assert "location" in summary
        assert summary["location"]["latitude"] == 51.5074
        assert summary["location"]["longitude"] == -0.1278
        assert summary["location"]["radius_km"] == 5.0
        
        assert "macro_targets" in summary
        assert summary["macro_targets"]["calories"] == 600
        assert summary["macro_targets"]["protein"] == 30
        assert summary["macro_targets"]["carbs"] == 70
        assert summary["macro_targets"]["fat"] == 15
    
    def test_build_summary_with_minimal_filters(self):
        """Test building summary with minimal filters."""
        filters = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278,
            query="pizza"
        )
        
        summary = filter_validation_service.build_filter_summary(filters)
        
        assert "search_terms" in summary
        assert summary["search_terms"]["general"] == "pizza"
        assert "meal" not in summary["search_terms"]
        
        assert summary["cuisines"] == []
        assert summary["dietary_restrictions"] == []
        
        assert "location" in summary
        assert "macro_targets" not in summary
    
    def test_build_summary_removes_empty_sections(self):
        """Test that empty sections are removed from summary."""
        filters = SearchFilterRequest(
            latitude=51.5074,
            longitude=-0.1278
        )
        
        summary = filter_validation_service.build_filter_summary(filters)
        
        assert "search_terms" not in summary
        assert "macro_targets" not in summary
        assert summary["cuisines"] == []
        assert summary["dietary_restrictions"] == []
