# app/models/user.py
"""User profile data models.

This module contains Pydantic models for user profiles and preferences.
"""
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, ConfigDict, BeforeValidator
from typing_extensions import Annotated
from app.utils.helper_functions import parse_datetime


class UserProfile(BaseModel):
    """User profile model.

    Attributes:
        id: Unique identifier (matches Supabase auth user ID)
        email: User's email address
        display_name: User's display name (optional)
        first_name: User's first name (optional)
        last_name: User's last name (optional)
        avatar: User's avatar (optional)
        is_active: Whether the user account is active
        is_pro: Whether the user has a subscription
        created_at: Profile creation timestamp
        updated_at: Profile last update timestamp
    """
    id: Annotated[str, Field(..., description="Unique identifier (matches Supabase auth user ID)")]
    email: Annotated[EmailStr, Field(..., description="User's email address")]
    display_name: Annotated[Optional[str], Field(None, description="User's display name(optional)")]
    first_name : Annotated[Optional[str], Field(None, description="User's first name(optional)")]
    last_name : Annotated[Optional[str], Field(None, description="User's last name(optional)")]
    age: Annotated[Optional[int], Field(None, description="User's age(optional)")]
    avatar_url : Annotated[Optional[str], Field(None, description="User's avatar(optional)")]
    is_active: Annotated[bool, Field(True, description="Whether the user account is active")]
    is_pro: Annotated[bool, Field(False, description="Whether the user has a subscription"), BeforeValidator(lambda x : bool(x))]
    created_at: Annotated[datetime, Field(False, description="Whether the user has a subscription"), BeforeValidator(parse_datetime)]
    updated_at: Annotated[datetime, Field(False, description="Whether the user has a subscription"), BeforeValidator(parse_datetime)]

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
    

class UserPreferences(BaseModel):
    """User dietary preferences model.

    Attributes:
        user_id: Reference to user profile ID
        dietary_restrictions: List of dietary restrictions (e.g., "vegetarian")
        favorite_cuisines: List of favorite cuisine types
        disliked_ingredients: List of ingredients the user dislikes
        calorie_target: Daily calorie target in kcal
        protein_target: Daily protein target in grams
        carbs_target: Daily carbohydrate target in grams
        fat_target: Daily fat target in grams
        created_at: Preferences creation timestamp
        updated_at: Preferences last update timestamp
    """
    user_id: str
    dietary_restrictions: List[str] = Field(default_factory=list)
    favorite_cuisines: List[str] = Field(default_factory=list)
    disliked_ingredients: List[str] = Field(default_factory=list)
    calorie_target: float = 2000.0
    protein_target: float = 150.0
    carbs_target: float = 200.0
    fat_target: float = 70.0
    created_at: datetime
    updated_at: datetime


class UpdateUserProfileRequest(BaseModel):
    """Request model for updating user profile.

    Attributes:
        display_name: New display name (optional)
        email: New email address (optional)
    """
    display_name: Annotated[Optional[str], Field(None, description="new display name")]
    email: Annotated[Optional[EmailStr], Field(None, description="new email address")]
    first_name: Annotated[Optional[str], Field(None, description="new first name")]
    last_name: Annotated[Optional[str], Field(None, description="new last name")]
    age: Annotated[Optional[int], Field(None, description="new age")]
    avatar_url: Annotated[Optional[str], Field(None, description="new avatar image")]


class UpdateUserPreferencesRequest(BaseModel):
    """Request model for updating user preferences.

    Attributes:
        dietary_restrictions: List of dietary restrictions
        favorite_cuisines: List of favorite cuisine types
        disliked_ingredients: List of ingredients the user dislikes
        calorie_target: Daily calorie target in kcal
        protein_target: Daily protein target in grams
        carbs_target: Daily carbohydrate target in grams
        fat_target: Daily fat target in grams
    """
    dietary_restrictions: Optional[List[str]] = None
    favorite_cuisines: Optional[List[str]] = None
    disliked_ingredients: Optional[List[str]] = None
    calorie_target: Optional[float] = None
    protein_target: Optional[float] = None
    carbs_target: Optional[float] = None
    fat_target: Optional[float] = None