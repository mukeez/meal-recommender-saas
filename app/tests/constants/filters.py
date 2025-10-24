"""Test constants for filter-related tests."""


from app.models.scan import CuisineType, DietaryRestriction

# Mock filter data
MOCK_CUISINES = ["italian", "chinese", "mexican"]
MOCK_DIETARY_RESTRICTIONS = ["vegan", "gluten_free", "halal"]

MOCK_SEARCH_FILTER_REQUEST = {
    "latitude": 51.5074,
    "longitude": -0.1278,
    "radius_km": 5.0,
    "query": "pizza",
    "meal_name": "margherita",
    "restaurant_name": "bella italia",
    "cuisines": [CuisineType.ITALIAN, CuisineType.MEXICAN],
    "dietary_restrictions": [DietaryRestriction.VEGAN, DietaryRestriction.GLUTEN_FREE],
    "dietary_preference": "vegetarian",
    "calories": 600.0,
    "protein": 30.0,
    "carbs": 70.0,
    "fat": 15.0,
    "limit": 50
}

MOCK_GOOGLE_PLACES_RESPONSE = [
    {
        "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
        "name": "Bella Italia",
        "geometry": {
            "location": {
                "lat": 51.5074,
                "lng": -0.1278
            }
        },
        "types": ["restaurant", "italian_restaurant", "food"],
        "rating": 4.5,
        "price_level": 2
    },
    {
        "place_id": "ChIJAbC123xyz",
        "name": "Taco Bell",
        "geometry": {
            "location": {
                "lat": 51.5080,
                "lng": -0.1285
            }
        },
        "types": ["restaurant", "mexican_restaurant", "fast_food"],
        "rating": 4.0,
        "price_level": 1
    }
]

MOCK_PLACE_DETAILS = {
    "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
    "name": "Bella Italia",
    "formatted_address": "123 Main St, London",
    "geometry": {
        "location": {
            "lat": 51.5074,
            "lng": -0.1278
        }
    },
    "rating": 4.5,
    "price_level": 2,
    "types": ["restaurant", "italian_restaurant", "food"],
    "website": "https://bellaitalia.com/menu",
    "formatted_phone_number": "+44 20 1234 5678",
    "photos": [
        {"photo_reference": "photo_ref_1"},
        {"photo_reference": "photo_ref_2"}
    ]
}

MOCK_MEAL_RECOMMENDATION = {
    "name": "Margherita Pizza",
    "description": "Classic tomato and mozzarella pizza",
    "macros": {
        "calories": 580,
        "protein": 25,
        "carbs": 70,
        "fat": 18
    },
    "match_score": 87,
    "estimated": True
}

MOCK_RESTAURANT_PIN = {
    "id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
    "google_place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
    "name": "Bella Italia",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "address": "123 Main St, London",
    "top_meal": {
        "name": "Margherita Pizza",
        "match_score": 87,
        "macros": {
            "calories": 580,
            "protein": 25,
            "carbs": 70,
            "fat": 18
        },
        "description": "Classic tomato and mozzarella pizza",
        "estimated": True
    },
    "rating": 4.5,
    "price_level": 2,
    "distance_km": 0.3,
    "cuisine_types": ["Italian"],
    "photo_url": None,
    "menu_url": "https://bellaitalia.com/menu"
}

MOCK_MAP_PINS_RESPONSE = {
    "pins": [MOCK_RESTAURANT_PIN],
    "total_count": 1,
    "search_center": {"lat": 51.5074, "lng": -0.1278},
    "search_radius_km": 5.0,
    "filters_applied": {
        "search_terms": {
            "general": "pizza"
        },
        "cuisines": ["italian"],
        "dietary_restrictions": ["vegan"],
        "dietary_preference": "vegetarian",
        "location": {
            "latitude": 51.5074,
            "longitude": -0.1278,
            "radius_km": 5.0,
            "address": None
        },
        "macro_targets": {
            "calories": 600,
            "protein": 30,
            "carbs": 70,
            "fat": 15
        }
    },
    "cached": False
}
