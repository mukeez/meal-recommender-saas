"""User endpoints for the meal recommendation API.

This module contains FastAPI routes for user-related functionality.
"""
from fastapi import APIRouter, Depends, Request

from api.auth_guard import auth_guard

router = APIRouter()


@router.get(
    "/me",
    summary="Get current user profile",
    description="Retrieve the profile of the currently authenticated user."
)
async def get_user_profile(request: Request, user=Depends(auth_guard)):
    """Get the current user's profile.

    This is a protected endpoint that requires authentication.

    Args:
        request: The incoming request
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        The user profile information
    """
    # You could fetch additional user data from a database here
    # For now, we just return the decoded JWT claims
    return {
        "id": user.get("sub"),
        "email": user.get("email"),
        "profile": {
            "authenticated": True,
            "auth_provider": user.get("aud"),
        }
    }


@router.get(
    "/preferences",
    summary="Get user preferences",
    description="Retrieve the dietary preferences for the currently authenticated user."
)
async def get_user_preferences(user=Depends(auth_guard)):
    """Get the current user's dietary preferences.

    This is a protected endpoint that requires authentication.

    Args:
        user: The authenticated user (injected by the auth_guard dependency)

    Returns:
        The user's dietary preferences
    """
    # In a real application, you would fetch this from a database
    # For now, we'll return mock data
    return {
        "user_id": user.get("sub"),
        "preferences": {
            "dietary_restrictions": ["gluten-free"],
            "favorite_cuisines": ["italian", "japanese"],
            "disliked_ingredients": ["mushrooms", "olives"],
            "calorie_target": 2000,
            "protein_target": 150,
            "carbs_target": 200,
            "fat_target": 70
        }
    }