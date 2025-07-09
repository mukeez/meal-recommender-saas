# app/models/user.py
"""User profile data models.

This module contains Pydantic models for user profiles and preferences.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict, BeforeValidator, field_validator, model_validator # Added model_validator
from typing_extensions import Annotated
from app.utils.helper_functions import parse_datetime, parse_date
from enum import Enum
from datetime import datetime, date



class HeightUnitPreference(str, Enum):
    """Height unit preference enumeration for user profiles."""
    METRIC = "metric"  # centimeters
    IMPERIAL = "imperial"  # inches


class WeightUnitPreference(str, Enum):
    """Weight unit preference enumeration for user profiles."""
    METRIC = "metric"  # kilograms
    IMPERIAL = "imperial"  # pounds



class Sex(str, Enum):
    """Sex enumeration for BMR calculation."""

    MALE = "male"
    FEMALE = "female"

class UserProfile(BaseModel):
    """User profile model.

    Attributes:
        id: Unique identifier (matches Supabase auth user ID)
        email: User's email address
        display_name: User's display name (optional)
        first_name: User's first name (optional)
        last_name: User's last name (optional)
        age: User's age (optional)
        dob: User's date of birth (optional)
        sex: User's biological sex (male/female)
        height: User's height. Input is expected in cm. The value of this attribute will be in cm if 'unit_preference' is 'metric', or in inches if 'imperial'.
        avatar_url: User's avatar (optional)
        is_active: Whether the user account is active
        is_pro: Whether the user has a subscription
        has_used_trial: Whether the user has used their free trial
        email_verified: Whether the user's email has been verified
        email_verification_token: Token for email verification
        email_verification_expires: When the email verification token expires
        fcm_token: Firebase Cloud Messaging token for push notifications (optional)
        meal_reminder_preferences_set: Whether the user has meal reminder preferences set (optional)
        has_macros: Whether the user has macro targets set
        unit_preference: Preferred unit system for measurements (metric/imperial)
        created_at: Profile creation timestamp
        updated_at: Profile last update timestamp
    """
    id: Annotated[str, Field(..., description="Unique identifier (matches Supabase auth user ID)")]
    email: Annotated[EmailStr, Field(..., description="User's email address")]
    display_name: Annotated[Optional[str], Field(None, description="User's display name(optional)")]
    first_name : Annotated[Optional[str], Field(None, description="User's first name(optional)")]
    last_name : Annotated[Optional[str], Field(None, description="User's last name(optional)")]
    age: Annotated[Optional[int], Field(None, description="User's age(optional)")]
    dob: Annotated[Optional[date], Field(None, description="User's date of birth (optional)"), BeforeValidator(parse_date)]
    sex: Annotated[Optional[Sex], Field(None, description="User's biological sex (male/female)")]
    height: Annotated[Optional[float], Field(None, description="User's height. Stored in cm, but returned in units based on height_unit_preference (cm for metric, inches for imperial).")]
    avatar_url : Annotated[Optional[str], Field(None, description="User's avatar(optional)")]
    is_active: Annotated[bool, Field(True, description="Whether the user account is active")]
    is_pro: Annotated[bool, Field(False, description="Whether the user has a subscription"), BeforeValidator(lambda x : bool(x))]
    has_used_trial: Annotated[bool, Field(False, description="Whether the user has used their free trial")]
    email_verified: Annotated[bool, Field(False, description="Whether the user's email has been verified")]
    fcm_token: Annotated[
        Optional[str],
        Field(
            None, description="Firebase Cloud Messaging token for push notifications"
        ),
    ]
    meal_reminder_preferences_set: Annotated[bool, Field(False, description="Whether the user has meal reminder preferences set")]
    has_macros: Annotated[bool, Field(False, description="Whether the user has macro targets set")]
    height_unit_preference: Annotated[HeightUnitPreference, Field(HeightUnitPreference.METRIC, description="Preferred unit for height measurements (metric: cm, imperial: inches)")]
    weight_unit_preference: Annotated[WeightUnitPreference, Field(WeightUnitPreference.METRIC, description="Preferred unit for weight measurements (metric: kg, imperial: lbs)")]

    created_at: Annotated[datetime, Field(..., description="Profile creation timestamp"), BeforeValidator(parse_datetime)]
    updated_at: Annotated[datetime, Field(..., description="Profile last update timestamp"), BeforeValidator(parse_datetime)]

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
        unit_preference: Preferred unit system for measurements (metric/imperial)
        created_at: Preferences creation timestamp
        updated_at: Preferences last update timestamp
    """
    user_id: str
    dietary_restrictions: List[str] = Field(default_factory=list)
    favorite_cuisines: List[str] = Field(default_factory=list)
    disliked_ingredients: List[str] = Field(default_factory=list)
    calorie_target: float = 0.0
    protein_target: float = 0.0
    carbs_target: float = 0.0
    fat_target: float = 0.0
    created_at: datetime
    updated_at: datetime


class UpdateUserProfileRequest(BaseModel):
    """Request model for updating user profile.

    Attributes:
        display_name: New display name (optional)
        first_name: New first name (optional)
        last_name: New last name (optional)
        age: New age (optional)
        dob: New date of birth (optional, format: YYYY-MM-DD)
        sex: New biological sex(male/female)
        height: New height in cm/ft (optional). If provided, 'unit_preference' must also be provided.
        avatar_url: New avatar image URL (optional)
        meal_reminder_preferences_set: Whether the user has meal reminder preferences set
        unit_preference: Preferred unit system for measurements (metric/imperial). Required if 'height' is provided.
    """
    display_name: Annotated[Optional[str], Field(None, description="new display name")]
    first_name: Annotated[Optional[str], Field(None, description="new first name")]
    last_name: Annotated[Optional[str], Field(None, description="new last name")]
    age: Annotated[Optional[int], Field(None, description="new age")]
    dob: Annotated[Optional[str], Field(None, description="new date of birth")]
    sex: Annotated[Optional[Sex], Field(None, description="new biological sex (male/female)")]
    height: Annotated[Optional[float], Field(None, description="new height. If provided, 'height_unit_preference' must also be specified. Assumed to be in cm if metric, inches if imperial.")] # Changed to float for consistency
    avatar_url: Annotated[Optional[str], Field(None, description="new avatar image")]
    meal_reminder_preferences_set: Annotated[Optional[bool], Field(None, description="Whether the user has meal reminder preferences set")] # Made optional for updates
    height_unit_preference: Annotated[Optional[HeightUnitPreference], Field(None, description="Preferred unit for height measurements (metric: cm, imperial: inches)")]
    weight_unit_preference: Annotated[Optional[WeightUnitPreference], Field(None, description="Preferred unit for weight measurements (metric: kg, imperial: lbs)")] # Made optional, but conditionally required

    @field_validator('dob')
    @classmethod
    def validate_dob(cls, v):
        """Validate that dob is a valid date string in ISO format (YYYY-MM-DD)."""
        if v is None:
            return v
            
        try:
            # Try to parse the string as a date
            date.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError("Date of birth must be a valid date string in ISO format (YYYY-MM-DD)")

    @model_validator(mode='after')
    def check_height_and_unit_preference(self) -> 'UpdateUserProfileRequest':
        if self.height is not None and self.height_unit_preference is None:
            raise ValueError("If 'height' is provided, 'height_unit_preference' must also be specified.")
        return self


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
        unit_preference: Preferred unit system for measurements (metric/imperial)
    """
    dietary_restrictions: Optional[List[str]] = None
    favorite_cuisines: Optional[List[str]] = None
    disliked_ingredients: Optional[List[str]] = None
    calorie_target: Optional[float] = None
    protein_target: Optional[float] = None
    carbs_target: Optional[float] = None
    fat_target: Optional[float] = None

