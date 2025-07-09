from enum import Enum


class ScanTestConstants(Enum):
    BARCODE = "5013665115953"
    SCAN_DATA = {
        "items": [
            {
                "name": "Kallø Lentil & Pea Veggie Cakes - Caramelised Onion Chutney Flavour",
                "quantity": "9.4g",  # Based on real OpenFoodFacts serving_quantity
                "calories": 41.0,  # Based on real energy-kcal_serving  
                "protein": 2.4,  # Based on real proteins_serving
                "carbs": 5.0,  # Based on real carbohydrates_serving
                "fat": 1.2,  # Based on real fat_serving
                "serving_unit": "grams",
                "amount": 9.4,
                "calories_per_gram": 4.361702127659575,  # 41 calories / 9.4g
                "protein_per_gram": 0.25531914893617025,  # 2.4g / 9.4g  
                "carbs_per_gram": 0.5319148936170213,  # 5g / 9.4g
                "fat_per_gram": 0.12765957446808511,  # 1.2g / 9.4g
            }
        ]
    }
    
    # Updated to reflect real OpenFoodFacts API response structure
    PRODUCT_DATA = {
        "barcode": "5013665115953",
        "product_name": "Lentil & Pea Veggie Cakes - Caramelised Onion Chutney Flavour",
        "brand_name": "Kallø",
        "ingredients": "Lentil & pea cake (82%) [red lentil (76%), green pea (6%)], rapeseed oil, Caramelised onion & balsamic vinegar seasoning (7%) [Onion powder (40%), tapioca maltodextrin, salt, rice flour, flavouring, natural flavouring, sunflower oil, maltodextrin (potato), acid: citric acid, balsamic vinegar). ALLERGEN ADVICE: May contain milk, soya & sesame seeds.",
        "nutrition_facts": {
            "name": "Kallø Lentil & Pea Veggie Cakes - Caramelised Onion Chutney Flavour",
            "calories": 41,
            "protein": 2.4,
            "carbs": 5.0,
            "fat": 1.2,
            "quantity": "9.4g",  # Real serving quantity from OpenFoodFacts
        },
        "gpt_nutrition_facts": None,  # Should be None when real data is available
        "created_at": "2025-04-14T15:25:07.454250Z",
    }
    
    # Sample OpenFoodFacts API response structure for testing
    OPENFOODFACTS_API_RESPONSE = {
        "brands": "Kallø",
        "ingredients_text": "Lentil & pea cake (82%) [red lentil (76%), green pea (6%)], rapeseed oil, Caramelised onion & balsamic vinegar seasoning (7%) [Onion powder (40%), tapioca maltodextrin, salt, rice flour, flavouring, natural flavouring, sunflower oil, maltodextrin (potato), acid: citric acid, balsamic vinegar). ALLERGEN ADVICE: May contain milk, soya & sesame seeds.",
        "product_name": "Lentil & Pea Veggie Cakes - Caramelised Onion Chutney Flavour",
        "serving_quantity": 9.4,
        "serving_quantity_unit": "g",
        "nutriments": {
            "carbohydrates_serving": 5.0,
            "proteins_serving": 2.4,
            "fat_serving": 1.2,
            "energy-kcal_serving": 41,
            # Additional fields that might be present but not required
            "carbohydrates_100g": 53.2,
            "proteins_100g": 25.5,
            "fat_100g": 12.8,
            "energy-kcal_100g": 436,
        },
        "code": "5013665115953"
    }
