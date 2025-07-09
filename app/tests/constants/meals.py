MOCK_RESTAURANT_DATA = [
    {'id': '44f642ad-96d8-4e9c-bfcb-d5d96155d9a0', 
     'name': 'The Botanist Reading', 
     'address': '1-5 King St, Reading RG1 2HB, United Kingdom', 
     'latitude': 51.4549992, 
     'longitude': -0.9695524, 
     'rating': '4.1', 
     'phone': '+44 118 959 5749', 
     'website': 'http://www.thebotanist.uk.com/locations/reading', ''
     'menu_url': '', 
     'menu_items': [{"name": "CAULIFLOWER WINGS", "description": "tossed in Frank\'s hot sauce"}, 
                    {"name": "SALT AND PEPPER CHICKEN WINGS", "description": "with sweet chilli dip"}]}]

MOCK_MEAL_ID = "123e4567-e89b-12d3-a456-426614174000"

MOCK_UPDATE_MEAL_DATA = {
    "name": "Updated Lunch",
    "description": "Updated chicken and rice",
    "calories": 600,
    "protein": 40,
    "carbs": 60,
    "fat": 20
}

MOCK_UPDATED_MEAL_RESPONSE = {
    "message": "Meal updated successfully",
    "meal": {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "user_id": "user-123",
        "name": "Updated Lunch",
        "description": "Updated chicken and rice",
        "calories": 600,
        "protein": 40,
        "carbs": 60,
        "fat": 20,
        "meal_time": "2025-05-31T12:00:00Z",
        "meal_type": "lunch"
    }
}

MOCK_DELETE_MEAL_RESPONSE = {
    "message": "Meal deleted successfully",
    "meal_id": "123e4567-e89b-12d3-a456-426614174000"
}