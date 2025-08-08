"""Pydantic models for scan-related endpoints.

This module contains all the request and response models used by the scanning
endpoints for food image analysis and barcode scanning.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


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