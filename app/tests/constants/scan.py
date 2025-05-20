from enum import Enum


class ScanTestConstants(Enum):
    BARCODE = "5013665115953"
    SCAN_DATA = {
        "items": [
            {
                "name": "Kallø Lentil & Pea Veggie Cakes - Caramelised Onion Chutney Flavour",
                "quantity": "1 cake (approximately 60g)",
                "calories": 150.0,
                "protein": 7.0,
                "carbs": 20.0,
                "fat": 5.0,
            }
        ]
    }
    PRODUCT_DATA = {
        "barcode": "5013665115953",
        "product_name": "Lentil & Pea Veggie Cakes - Caramelised Onion Chutney Flavour",
        "brand_name": "Kallø",
        "ingredients": "Lentil & pea cake (82%) [red lentil (76%), green pea (6%)], rapeseed oil, Caramelised onion & balsamic vinegar seasoning (7%) [Onion powder (40%), tapioca maltodextrin, salt, rice flour, flavouring, natural flavouring, sunflower oil, maltodextrin (potato), acid: citric acid, balsamic vinegar). ALLERGEN ADVICE: May contain milk, soya & sesame seeds.",
        "nutrition_facts": None,
        "gpt_nutrition_facts": {
            "name": "Kallø Lentil & Pea Veggie Cakes - Caramelised Onion Chutney Flavour",
            "calories": 150,
            "protein": 7.0,
            "carbs": 20.0,
            "fat": 5.0,
            "quantity": "1 cake (approximately 60g)",
        },
        "created_at": "2025-04-14T15:25:07.454250Z",
    }
