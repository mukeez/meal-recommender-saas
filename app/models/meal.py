"""Data models for meal recommendation API.

This module contains Pydantic models that define the structure of request and
response data for the meal recommendation API.
"""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional, Dict
from typing_extensions import Annotated
from pydantic import BaseModel, field_validator, Field, BeforeValidator
from app.utils.helper_functions import parse_datetime
from typing_extensions import Annotated
from app.models.product import Product
from app.utils.constants import ServingUnit


class MacroNutrients(BaseModel):
    """Macro nutrient requirements or estimates.

    Attributes:
        calories: Target calories in kcal
        protein: Target protein in grams
        carbs: Target carbohydrates in grams
        fat: Target fat in grams
    """

    calories: float
    protein: float
    carbs: float
    fat: float

    @field_validator("calories", "protein", "carbs", "fat")
    def validate_positive(cls, value: float) -> float:
        """Validate that nutrient values are positive."""
        if value < 0:
            raise ValueError("Nutrient values must be positive")
        return value


class MealSuggestionRequest(BaseModel):
    """Request model for meal suggestions.

    Attributes:
        location: Geographic location for restaurant search
        calories: Target calories in kcal
        protein: Target protein in grams
        carbs: Target carbohydrates in grams
        fat: Target fat in grams
    """

    location: Annotated[str, Field(..., description="normalized address for restaurant search")]
    longitude: Annotated[float, Field(..., description="Longitude coordinate")]
    latitude: Annotated[float, Field(..., description="Latitude coordinate")]
    calories: Annotated[float, Field(..., description="Target calories in kcal")]
    protein: Annotated[float, Field(..., description="Target protein in grams")]
    carbs: Annotated[float, Field(..., description="Target carbohydrates in grams")]
    fat: Annotated[float, Field(..., description="Target fat in grams")]
    dietary_restrictions: Optional[List[str]] = Field(
        None, 
        description="List of dietary restrictions (e.g., vegan, gluten-free, etc.)"
    )
    dietary_preference: Optional[str] = Field(
        None, 
        description="vegan, keto, etc. If not provided"
    )


    @field_validator("calories", "protein", "carbs", "fat")
    def validate_positive(cls, value: float) -> float:
        """Validate that nutrient values are positive."""
        if value < 0:
            raise ValueError("Macro values must be positive")
        return value


class Restaurant(BaseModel):
    """Restaurant information.

    Attributes:
        name: Restaurant name
        location: Restaurant address or location description
    """

    name: str
    location: Optional[str] = None


class MealSuggestion(BaseModel):
    """Meal suggestion model.

    Attributes:
        name: Name of the suggested meal
        description: Brief description of the meal
        macros: Estimated macro nutrients
        restaurant: Source restaurant information
    """

    name: str
    description: str
    macros: MacroNutrients
    restaurant: Restaurant

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Grilled Chicken Salad",
                "description": "Fresh salad with grilled chicken breast, mixed greens, and light dressing",
                "macros": {"calories": 450, "protein": 35, "carbs": 30, "fat": 15},
                "restaurant": {
                    "name": "Healthy Bites",
                    "location": "123 Main St, Finchley",
                },
            }
        }
    }


class MealSuggestionResponse(BaseModel):
    """Response model for meal suggestions.

    Attributes:
        meals: List of meal suggestions
    """

    meals: List[MealSuggestion]


class MealType(str, Enum):
    """Enumeration of meal types based on time of day."""
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    OTHER = "other"


class LoggingMode(str, Enum):
    """Enumeration of meal logging modes."""
    MANUAL = "manual"
    BARCODE = "barcode"
    SCANNED = "scanned"


class ServingUnitEnum(str, Enum):
    """Enumeration of serving size units."""
    GRAMS = "grams"
    CUP = "cup"
    TABLESPOON = "tablespoon"
    PIECE = "piece"
    PLATE = "plate"
    SCOOP = "scoop"
    SLICE = "slice"
    MILL = "mill"


class LogMealRequest(BaseModel):
    """Request model for logging a meal.

    Attributes:
        name: Name of the meal
        description: Description of the meal
        protein: Protein amount in grams
        carbs: Carbohydrate amount in grams
        fat: Fat amount in grams
        calories: Total calories
        meal_time: Timestamp of when the meal was consumed
        meal_type: Type of meal (optional, auto-classified if not provided)
        logging_mode: How the meal was logged (manual, barcode, scanned)
        notes: Additional notes about the meal
        serving_size: Size of one serving (converted to grams for storage)
        serving_unit: Unit of measurement for serving size (input unit)
        number_of_servings: Number of servings consumed
        favorite: Whether the meal is marked as a favorite
    """

    name: str = Field(..., description="Name of the meal")
    description: Optional[str] = Field(None, description="Description of the meal")
    protein: float = Field(..., description="Protein amount in grams per serving", ge=0)
    carbs: float = Field(..., description="Carbohydrate amount in grams per serving", ge=0)
    fat: float = Field(..., description="Fat amount in grams per serving", ge=0)
    calories: float = Field(..., description="Total calories per serving", ge=0)
    meal_time: Annotated[Optional[datetime],Field(
        default_factory=datetime.now, description="Timestamp of meal consumption")]
    meal_type: Optional[MealType] = Field(
        None, 
        description="Type of meal (breakfast, lunch, dinner, other). Will be auto-classified if not provided."
    )
    logging_mode: LoggingMode = Field(
        LoggingMode.MANUAL,
        description="How the meal was logged (manual, barcode, scanned)"
    )
    notes: Optional[str] = Field(None, description="Additional notes about the meal")
    serving_unit: ServingUnitEnum = Field(ServingUnitEnum.GRAMS, description="Unit of measurement for serving")
    amount: float = Field(1.0, description="Amount/quantity of the serving unit", ge=1.0)
    favorite: Optional[bool] = Field(False, description="Whether the meal is marked as a favorite")


class UpdateMealRequest(BaseModel):
    """Request model for updating a logged meal.

    Attributes:
        name: Name of the meal (optional)
        description: Description of the meal (optional)
        protein: Protein amount in grams per serving (optional)
        carbs: Carbohydrate amount in grams per serving (optional)
        fat: Fat amount in grams per serving (optional)
        calories: Total calories per serving (optional)
        meal_time: Timestamp of when the meal was consumed (optional)
        meal_type: Type of meal (optional)
        logging_mode: How the meal was logged (optional)
        notes: Additional notes about the meal (optional)
        serving_size: Size of one serving (optional)
        serving_unit: Unit of measurement for serving size (optional)
        number_of_servings: Number of servings consumed (optional)
        favorite: Whether the meal is marked as a favorite (optional)
    """

    name: Optional[str] = Field(None, description="Name of the meal")
    description: Optional[str] = Field(None, description="Description of the meal")
    protein: Optional[float] = Field(None, description="Protein amount in grams per serving", ge=0)
    carbs: Optional[float] = Field(None, description="Carbohydrate amount in grams per serving", ge=0)
    fat: Optional[float] = Field(None, description="Fat amount in grams per serving", ge=0)
    calories: Optional[float] = Field(None, description="Total calories per serving", ge=0)
    meal_time: Optional[datetime] = Field(None, description="Timestamp of meal consumption")
    meal_type: Optional[MealType] = Field(None, description="Type of meal (breakfast, lunch, dinner, other)")
    logging_mode: Optional[LoggingMode] = Field(None, description="How the meal was logged (manual, barcode, scanned)")
    notes: Optional[str] = Field(None, description="Additional notes about the meal")
    serving_unit: Optional[ServingUnitEnum] = Field(None, description="Unit of measurement for serving")
    amount: Optional[float] = Field(None, description="Amount/quantity of the serving unit", ge=1.0)
    favorite: Optional[bool] = Field(None, description="Whether the meal is marked as a favorite")


class LoggedMeal(BaseModel):
    """Logged meal model with additional tracking information.

    Attributes:
        id: Unique identifier for the meal
        user_id: ID of the user who logged the meal
        name: Name of the meal
        description: Description of the meal
        calories: Total calories consumed (all servings)
        protein: Total protein consumed in grams (all servings)
        carbs: Total carbohydrates consumed in grams (all servings)
        fat: Total fat consumed in grams (all servings)
        meal_time: Timestamp when the meal was logged (ISO format)
        meal_type: Type of meal (breakfast, lunch, dinner, other)
        logging_mode: How the meal was logged (manual, barcode, scanned)
        photo_url: URL to the meal photo (optional)
        created_at: Timestamp when the meal was created (ISO format)
        notes: Additional notes about the meal
        serving_size: Size of one serving in grams (stored value)
        number_of_servings: Number of servings consumed
        favorite: Whether the meal is marked as a favorite
    """

    id: str = Field(..., description="Unique identifier for the meal")
    user_id: str = Field(..., description="ID of the user who logged the meal")
    name: str = Field(..., description="Name of the meal")
    description: Optional[str] = Field(None, description="Description of the meal")
    calories: int = Field(..., description="Total calories consumed (all servings)")
    protein: float = Field(..., description="Total protein consumed in grams (all servings)")
    carbs: float = Field(..., description="Total carbohydrates consumed in grams (all servings)")
    fat: float = Field(..., description="Total fat consumed in grams (all servings)")
    meal_time: Annotated[datetime, Field(..., description="ISO format timestamp when the meal was logged")]
    meal_type: MealType = Field(
        MealType.OTHER, 
        description="Classification of the meal based on time of day"
    )
    logging_mode: LoggingMode = Field(
        LoggingMode.MANUAL,
        description="How the meal was logged (manual, barcode, scanned)"
    )
    photo_url: Optional[str] = Field(None, description="URL to the meal photo")
    created_at: Annotated[
        datetime,
        Field(..., description="ISO format timestamp when the meal was created"),
        BeforeValidator(parse_datetime),
    ]
    notes: Optional[str] = Field(None, description="Additional notes about the meal")
    serving_unit: ServingUnitEnum = Field(..., description="Unit of measurement for serving")
    amount: float = Field(..., description="Amount/quantity of the serving unit")
    read_only: bool = Field(..., description="Whether serving_unit is read-only (true for barcode/scanned meals)")
    favorite: bool = Field(False, description="Whether the meal is marked as a favorite")


class UpdateMealResponse(BaseModel):
    """Response model for meal update operations.

    Attributes:
        message: Success message
        meal: The updated meal data
    """
    message: str = Field(..., description="Success message")
    meal: LoggedMeal = Field(..., description="The updated meal data")


class DeleteMealResponse(BaseModel):
    """Response model for meal deletion operations.

    Attributes:
        message: Success message
        meal_id: ID of the deleted meal
    """
    message: str = Field(..., description="Success message")
    meal_id: str = Field(..., description="ID of the deleted meal")


class DailyProgressResponse(BaseModel):
    """Response model for daily macro progress.

    Attributes:
        logged_macros: Macros logged for the day
        target_macros: User's daily macro targets
        progress_percentage: Percentage of macro targets achieved
    """

    logged_macros: MacroNutrients
    target_macros: MacroNutrients
    progress_percentage: Dict[str, float]


class MacroSummary(BaseModel):
    """Summary of macro intake for a time period (day, week, month)."""
    period_label: str  # e.g., "Mon", "W1", "January"
    date: date  # Reference date for the period
    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0


class ProgressSummary(BaseModel):
    """Summary of progress for a time period with new aggregation."""
    period_macros: List[MacroSummary]  # Renamed from daily_macros
    average_macros: MacroNutrients
    target_macros: MacroNutrients
    comparison_percentage: Dict[str, float]
    start_date: date
    end_date: date
    period_type: str  # "weekdays", "weeks", "months"
    aggregation_period: str  # "1w", "1m", "3m", etc.
    days_with_logs: int
    total_days: int


class DailyMacroSummary(BaseModel):
    """Summary of daily macro intake for progress tracking."""
    date: date
    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0


class MealSearchRequest(BaseModel):
    """Request model for searching meal logs and products.

    Attributes:
        query: Search term for food item name
        meal_type: Filter by meal type (optional)
        start_date: Start date for search range (optional)
        end_date: End date for search range (optional)
        limit: Maximum number of results to return (default: 20)
        favorites_only: Filter to show only favorite meals (optional)
    """
    query: str = Field(..., description="Search term for food item name", min_length=1)
    meal_type: Optional[MealType] = Field(None, description="Filter by meal type")
    start_date: Optional[date] = Field(None, description="Start date for search range")
    end_date: Optional[date] = Field(None, description="End date for search range")
    limit: int = Field(20, description="Maximum number of results", ge=1, le=100)
    favorites_only: Optional[bool] = Field(None, description="Filter to show only favorite meals")


class LoggedMealWithBarcode(BaseModel):
    """Product-based meal model with barcode for product suggestions.

    Similar to LoggedMeal but with optional/null fields for product context:
        barcode: Product barcode identifier
        meal_time: null for products
        meal_type: null for products  
        created_at: null for products
        user_id: not needed for products
    """
    id: str = Field(..., description="Unique identifier for the meal")
    name: str = Field(..., description="Name of the meal")
    description: Optional[str] = Field(None, description="Description of the meal")
    calories: int = Field(..., description="Total calories consumed (all servings)")
    protein: float = Field(..., description="Total protein consumed in grams (all servings)")
    carbs: float = Field(..., description="Total carbohydrates consumed in grams (all servings)")
    fat: float = Field(..., description="Total fat consumed in grams (all servings)")
    meal_time: Optional[datetime] = Field(None, description="Null for product suggestions")
    meal_type: Optional[MealType] = Field(None, description="Null for product suggestions")
    logging_mode: LoggingMode = Field(LoggingMode.BARCODE, description="How the meal was logged")
    photo_url: Optional[str] = Field(None, description="URL to the meal photo")
    created_at: Optional[datetime] = Field(None, description="Null for product suggestions")
    notes: Optional[str] = Field(None, description="Additional notes about the meal")
    serving_unit: ServingUnitEnum = Field(..., description="Unit of measurement for serving")
    amount: float = Field(..., description="Amount/quantity of the serving unit")
    read_only: bool = Field(True, description="Always true for barcode-based meals")
    favorite: bool = Field(False, description="Whether the meal is marked as a favorite")
    barcode: str = Field(..., description="Product barcode identifier")


class MealSearchResponse(BaseModel):
    """Response model for meal search results.

    Attributes:
        results: List of matching logged meals
        total_results: Total count of logged meals found
        search_query: The search term that was used
    """
    results: List[LoggedMeal] = Field(default_factory=list, description="Matching logged meals")
    total_results: int = Field(0, description="Total count of logged meals found")
    search_query: str = Field(..., description="The search term that was used")


class ProductMealSearchResponse(BaseModel):
    """Response model for product search results in meal format.

    Attributes:
        results: List of products converted to meal format with barcodes
        total_results: Total count of products found
        search_query: The search term that was used
    """
    results: List[LoggedMealWithBarcode] = Field(default_factory=list, description="Products converted to meal format with barcodes")
    total_results: int = Field(0, description="Total count of products found")
    search_query: str = Field(..., description="The search term that was used")


class CalculateMacrosRequest(BaseModel):
    """Request model for calculating macros based on amount changes.

    Attributes:
        base_calories: Base calories for the meal
        base_protein: Base protein for the meal (grams)
        base_carbs: Base carbohydrates for the meal (grams)
        base_fat: Base fat for the meal (grams)
        base_amount: Original amount/quantity
        new_amount: New amount/quantity to calculate macros for
    """
    base_calories: float = Field(..., description="Base calories for the meal", ge=0)
    base_protein: float = Field(..., description="Base protein for the meal (grams)", ge=0)
    base_carbs: float = Field(..., description="Base carbohydrates for the meal (grams)", ge=0)
    base_fat: float = Field(..., description="Base fat for the meal (grams)", ge=0)
    base_amount: float = Field(..., description="Original amount/quantity", ge=0)
    new_amount: float = Field(..., description="New amount/quantity to calculate macros for", ge=0)


class CalculateMacrosResponse(BaseModel):
    """Response model for calculated macros.

    Attributes:
        calories: Calculated calories
        protein: Calculated protein (grams)
        carbs: Calculated carbohydrates (grams)
        fat: Calculated fat (grams)
    """
    calories: float = Field(..., description="Calculated calories")
    protein: float = Field(..., description="Calculated protein (grams)")
    carbs: float = Field(..., description="Calculated carbohydrates (grams)")
    fat: float = Field(..., description="Calculated fat (grams)")
