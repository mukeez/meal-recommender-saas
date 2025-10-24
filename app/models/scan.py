"""Pydantic models for scan-related endpoints.

This module contains all the request and response models used by the scanning
endpoints for food image analysis and barcode scanning.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class CuisineType(str, Enum):
    """Standardized cuisine types for filtering."""
    ITALIAN = "italian"
    CHINESE = "chinese"
    MEXICAN = "mexican"
    JAPANESE = "japanese"
    INDIAN = "indian"
    AFRICAN = "african"
    GHANAIAN = "ghanaian"
    NIGERIAN = "nigerian"
    ETHIOPIAN = "ethiopian"
    AMERICAN = "american"
    FRENCH = "french"
    THAI = "thai"
    MEDITERRANEAN = "mediterranean"
    MIDDLE_EASTERN = "middle_eastern"
    KOREAN = "korean"
    VIETNAMESE = "vietnamese"
    GREEK = "greek"
    SPANISH = "spanish"
    CARIBBEAN = "caribbean"
    BRAZILIAN = "brazilian"
    TURKISH = "turkish"
    LEBANESE = "lebanese"
    PERSIAN = "persian"
    MOROCCAN = "moroccan"
    PAKISTANI = "pakistani"


class DietaryRestriction(str, Enum):
    """Standardized dietary restrictions."""
    VEGAN = "vegan"
    VEGETARIAN = "vegetarian"
    GLUTEN_FREE = "gluten_free"
    DAIRY_FREE = "dairy_free"
    NUT_FREE = "nut_free"
    HALAL = "halal"
    KOSHER = "kosher"
    PESCATARIAN = "pescatarian"
    KETO = "keto"
    PALEO = "paleo"
    LOW_CARB = "low_carb"
    SOY_FREE = "soy_free"
    EGG_FREE = "egg_free"
    SHELLFISH_FREE = "shellfish_free"


class FoodItem(BaseModel):
    """Food item with nutritional information.

    Attributes:
        name: Name of the food item
        amount: Amount/serving size as numeric value
        serving_unit: Unit of measurement (always "grams")
        calories: Calories in kcal
        protein: Protein in grams
        carbs: Carbohydrates in grams
        fat: Fat in grams
        calories_per_gram: Calories per gram for easy calculation
        protein_per_gram: Protein per gram for easy calculation
        carbs_per_gram: Carbs per gram for easy calculation
        fat_per_gram: Fat per gram for easy calculation
    """

    name: str
    amount: float
    serving_unit: str = "grams"
    calories: float
    protein: float
    carbs: float
    fat: float
    calories_per_gram: float
    protein_per_gram: float
    carbs_per_gram: float
    fat_per_gram: float


class SimilarDish(BaseModel):
    """Similar dish found through vector search.
    
    Attributes:
        id: Unique identifier for the dish
        dish_name: Name of the similar dish
        country: Optional country of origin
        description: Optional description of the dish
        similarity: Similarity score (0.0 to 1.0)
        calories: Estimated calories in grams
        protein: Estimated protein in grams
        carbs: Estimated carbs in grams
        fat: Estimated fat in grams
        serving_unit: Always "grams"
        amount: Amount in grams, default is 100g for nutritional estimates
    """
    id: Optional[int] = Field(None, description="Unique identifier for the dish")
    dish_name: str = Field(..., description="Name of the similar dish")
    country: Optional[str] = Field(None, description="Country of origin")
    description: Optional[str] = Field(None, description="Dish description")
    similarity: float = Field(..., description="Similarity score (0.0 to 1.0)")
    calories: Optional[float] = Field(None, description="Estimated calories in grams")
    protein: Optional[float] = Field(None, description="Estimated protein in grams")
    carbs: Optional[float] = Field(None, description="Estimated carbs in grams")
    fat: Optional[float] = Field(None, description="Estimated fat in grams")
    serving_unit: str = Field("grams", description="Serving unit, always 'grams'")
    amount: float = Field(100.0, description="Amount in grams, default is 100g for nutritional estimates")


class IndigenousClassification(BaseModel):
    """Indigenous dish classification result.
    
    Attributes:
        is_indigenous: Whether the dish is classified as indigenous
        confidence: Confidence score (0.0 to 1.0)
        country_of_origin: Country of origin if indigenous
        dish_classification: Traditional/Fusion/International classification
        reasoning: Explanation of the classification decision
    """
    is_indigenous: bool = Field(..., description="Whether the dish is classified as indigenous")
    confidence: float = Field(..., description="Confidence score (0.0 to 1.0)")
    country_of_origin: Optional[str] = Field(None, description="Country of origin if indigenous")
    dish_classification: str = Field(..., description="Traditional/Fusion/International classification")
    reasoning: str = Field(..., description="Explanation of the classification decision")


class ScanResponse(BaseModel):
    """Response model for basic scan endpoints.

    Attributes:
        items: List of food items with nutritional information
    """
    items: List[FoodItem]


class EnhancedScanResponse(BaseModel):
    """Enhanced response model for scan endpoints with vector search results and indigenous classification.
    
    Attributes:
        items: Nutritional analysis from AI
        similar_dishes: Similar dishes from vector search
        detected_ingredients: Individual ingredients detected in the meal
        search_method: Method used: 'vector_search', 'llm_fallback', or 'both'
        message: Additional information about the search process
        confidence_explanation: Explanation of why vector search was used or not
        indigenous_classification: Indigenous dish classification result
    """
    items: List[FoodItem] = Field(..., description="Nutritional analysis from AI")
    similar_dishes: List[SimilarDish] = Field(default_factory=list, description="Similar dishes from vector search")
    detected_ingredients: List[str] = Field(default_factory=list, description="Individual ingredients detected in the meal")
    search_method: str = Field(..., description="Method used: 'vector_search', 'llm_fallback', or 'both'")
    message: Optional[str] = Field(None, description="Additional information about the search process")
    confidence_explanation: Optional[str] = Field(None, description="Explanation of why vector search was used or not")
    indigenous_classification: Optional[IndigenousClassification] = Field(None, description="Indigenous dish classification result")


class ScanToMealRequest(BaseModel):
    """Request model for converting scan data to meal logging format.
    
    Attributes:
        food_item: The scanned food item data
        desired_amount: The amount the user wants to log (in grams)
        notes: Optional notes for the meal
        favorite: Whether to mark as favorite
    """
    food_item: FoodItem
    desired_amount: float = Field(..., gt=0, description="Desired amount in grams")
    notes: Optional[str] = Field(None, description="Optional notes for the meal")
    favorite: bool = Field(False, description="Whether to mark as favorite")


class ScanToMealResponse(BaseModel):
    """Response model for converted meal data.
    
    Attributes:
        name: Meal name
        calories: Calculated calories for desired amount
        protein: Calculated protein for desired amount  
        carbs: Calculated carbs for desired amount
        fat: Calculated fat for desired amount
        serving_unit: Always "grams"
        amount: Desired amount in grams
        notes: Optional notes
        favorite: Whether marked as favorite
        logging_mode: Set to "scanned"
    """
    name: str
    calories: float
    protein: float
    carbs: float
    fat: float
    serving_unit: str = "grams"
    amount: float
    notes: Optional[str] = None
    favorite: bool = False
    logging_mode: str = "scanned"


class TopMealPreview(BaseModel):
    """Preview of top recommended meal at a restaurant."""
    name: str = Field(..., description="Meal name")
    match_score: int = Field(..., ge=0, le=100, description="Match percentage (0-100)")
    macros: dict = Field(..., description="Estimated macros (calories, protein, carbs, fat)")
    description: Optional[str] = Field(None, max_length=150, description="Brief meal description")
    estimated: bool = Field(True, description="Whether macros are LLM-estimated")


class RestaurantPin(BaseModel):
    """Restaurant data optimized for map pin display."""
    id: str = Field(..., description="Database UUID")
    google_place_id: str = Field(..., description="Google Places ID")
    name: str = Field(..., description="Restaurant name")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    address: str = Field(..., description="Full address")
    
    # Top meal preview (None if match score < 50%)
    top_meal: Optional[TopMealPreview] = Field(None, description="Top recommended meal")
    
    # Visual indicators
    rating: Optional[float] = Field(None, ge=0, le=5, description="Google rating")
    price_level: Optional[int] = Field(None, ge=1, le=4, description="Price level (1=cheap, 4=expensive)")
    distance_km: Optional[float] = Field(None, description="Distance from search center")
    
    # Categorization
    cuisine_types: List[str] = Field(default_factory=list, description="Cuisine categories")
    photo_url: Optional[str] = Field(None, description="Primary photo URL (for future use)")
    menu_url: Optional[str] = Field(None, description="Menu URL if available")


class MapPinsRequest(BaseModel):
    """Request parameters for map pins endpoint."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")
    
    # Search parameters
    radius_km: float = Field(default=5.0, ge=0.1, le=50, description="Search radius in kilometers")
    query: Optional[str] = Field(None, max_length=100, description="Search query (cuisine type, restaurant name)")
    
    # Macro targets for match scoring
    calories: Optional[float] = Field(None, ge=0, description="Target calories")
    protein: Optional[float] = Field(None, ge=0, description="Target protein (grams)")
    carbs: Optional[float] = Field(None, ge=0, description="Target carbs (grams)")
    fat: Optional[float] = Field(None, ge=0, description="Target fat (grams)")
    
    # Filters
    dietary_restrictions: Optional[List[str]] = Field(None, description="Dietary restrictions")
    dietary_preference: Optional[str] = Field(None, description="Dietary preference (e.g., vegetarian)")
    cuisine_types: Optional[List[str]] = Field(None, description="Filter by cuisine types")
    
    # Pagination
    limit: int = Field(default=50, ge=1, le=200, description="Maximum number of results")


class MapPinsResponse(BaseModel):
    """Response containing restaurant pins for map display."""
    pins: List[RestaurantPin] = Field(default_factory=list, description="Restaurant pins")
    total_count: int = Field(..., description="Total restaurants found")
    search_center: dict = Field(..., description="Search center coordinates {lat, lng}")
    search_radius_km: float = Field(..., description="Search radius used")
    filters_applied: dict = Field(default_factory=dict, description="Summary of filters applied")
    cached: bool = Field(False, description="Whether response was from cache")