from enum import Enum


class UserTestConstants(Enum):
    MOCK_USER_ID = "d957fd38-cbdf-48b5-8ffa-a5d1d8142372"
    MOCK_USER_EMAIL = "matrix@simulation.com"
    MOCK_USER_PASSWORD = "testPasswo@d"
    MOCK_USER_DISPLAY_NAME = "matrix"
    MOCK_CUSTOMER_ID = "cus_test_123"
    MOCK_USER_PROFILE_DATA = {
        "id": MOCK_USER_ID,
        "email": MOCK_USER_EMAIL,
        "display_name": MOCK_USER_DISPLAY_NAME,
        "first_name": "Matrix",
        "last_name": "Schrodinger",
        "avatar_url": "https://mzlpkriykyspqskncion.supabase.co/storage/v1/object/public/avatars/e269b58e-5e72-46d2-b2ef-5df7f35622ef/avatar.png",
        "is_active": True,
        "is_pro": False,
        "created_at": "2025-05-14T18:42:34.623132Z",
        "updated_at": "2025-05-14T18:42:34.623132Z",
    }

    MOCK_USER_PREFERENCES_DATA = {
        "user_id": MOCK_USER_ID,
        "dietary_restrictions": ["milk"],
        "favorite_cuisines": ["jollof"],
        "disliked_ingredients": ["paparika"],
        "calorie_target": 2000.0,
        "protein_target": 150.0,
        "carbs_target": 200.0,
        "fat_target": 70.0,
        "created_at": "2025-04-14T15:25:07.454224Z",
        "updated_at": "2025-04-14T15:25:07.454250Z",
    }
