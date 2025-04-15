"""Scanning endpoints for the meal recommendation API.

This module contains FastAPI routes for scanning barcodes and food images
to retrieve nutritional information.
"""
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Body
from fastapi.responses import JSONResponse
import httpx
import logging
import base64
import os
from typing import List, Optional
from pydantic import BaseModel

from app.api.auth_guard import auth_guard
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Models
class FoodItem(BaseModel):
    """Food item with nutritional information.

    Attributes:
        name: Name of the food item
        quantity: Quantity/serving size
        calories: Calories in kcal
        protein: Protein in grams
        carbs: Carbohydrates in grams
        fat: Fat in grams
    """
    name: str
    quantity: str
    calories: float
    protein: float
    carbs: float
    fat: float


class ScanResponse(BaseModel):
    """Response model for scan endpoints.

    Attributes:
        items: List of food items with nutritional information
    """
    items: List[FoodItem]


@router.post(
    "/barcode",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Scan barcode for nutritional information",
    description="Scan a UPC barcode and retrieve nutritional information using Nutritionix API."
)
async def scan_barcode(
        barcode: str = Body(..., embed=True),
        user=Depends(auth_guard)
) -> ScanResponse:
    """Scan a UPC barcode to get nutritional information.

    Args:
        barcode: UPC barcode number
        user: Authenticated user (from auth_guard dependency)

    Returns:
        Nutritional information for the scanned product

    Raises:
        HTTPException: If the barcode is invalid or not found
    """
    try:
        if not barcode.isdigit():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid barcode format. Barcode must contain only digits."
            )

        nutritionix_app_id = os.getenv("NUTRITIONIX_APP_ID")
        nutritionix_api_key = os.getenv("NUTRITIONIX_API_KEY")

        if not nutritionix_app_id or not nutritionix_api_key:
            logger.error("Nutritionix API credentials not configured")
            return HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Nutrition service not properly configured"
            )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://trackapi.nutritionix.com/v2/search/item",
                headers={
                    "x-app-id": nutritionix_app_id,
                    "x-app-key": nutritionix_api_key
                },
                params={
                    "upc": barcode
                }
            )

            if response.status_code != 200:
                logger.error(f"Nutritionix API error: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Barcode not found or invalid"
                )

            data = response.json()
            if "foods" not in data or len(data["foods"]) == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No nutritional information found for this barcode"
                )

            food = data["foods"][0]
            food_item = FoodItem(
                name=food.get("food_name", "Unknown"),
                quantity=f"{food.get('serving_qty', 1)} {food.get('serving_unit', 'serving')}",
                calories=food.get("nf_calories", 0),
                protein=food.get("nf_protein", 0),
                carbs=food.get("nf_total_carbohydrate", 0),
                fat=food.get("nf_total_fat", 0)
            )

            return ScanResponse(items=[food_item])

    except httpx.RequestError as e:
        logger.error(f"Error communicating with Nutritionix API: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error communicating with nutrition service"
        )

    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise

    except Exception as e:
        logger.error(f"Unexpected error scanning barcode: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing barcode: {str(e)}"
        )


@router.post(
    "/image",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze food image for nutritional information",
    description="Upload a food image and get nutritional information using vision AI."
)
async def scan_image(
        image: UploadFile = File(...),
        user=Depends(auth_guard)
) -> ScanResponse:
    """Analyze a food image to estimate nutritional content.

    Args:
        image: Uploaded food image
        user: Authenticated user (from auth_guard dependency)

    Returns:
        Estimated nutritional information for food items in the image

    Raises:
        HTTPException: If the image analysis fails
    """
    try:
        logger.info(f"Received image upload: filename={image.filename}, content_type={image.content_type}")

        try:
            contents = await image.read()
            logger.info(f"Successfully read image file, size={len(contents)} bytes")
        except Exception as e:
            logger.error(f"Error reading image file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error reading uploaded file: {str(e)}"
            )

        if not contents or len(contents) == 0:
            logger.error("Uploaded file is empty")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty"
            )

        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(contents))
            img_format = img.format
            logger.info(f"Image format detected: {img_format}, size: {img.size}")
        except Exception as e:
            logger.error(f"Error validating image format: {str(e)}")
            logger.error("This may not be a valid image file")

        try:
            encoded_image = base64.b64encode(contents).decode("utf-8")
            logger.info(f"Successfully base64 encoded image, encoded_size={len(encoded_image)}")
        except Exception as e:
            logger.error(f"Error encoding image to base64: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing image: {str(e)}"
            )

        openai_api_key = settings.OPENAI_API_KEY
        if not openai_api_key:
            logger.error("OpenAI API key not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Vision service not properly configured: API key missing"
            )

        model_name = "gpt-4o-mini"
        logger.info(f"Using vision model: {model_name}")

        prompt = """Analyze this food image and identify all food items.
For each food item, provide:
1. Name of the food
2. Estimated quantity (e.g., "1 serving", "150g", "1 cup")
3. Estimated calories
4. Estimated protein (g)
5. Estimated carbs (g) 
6. Estimated fat (g)

Format your response as a valid JSON object with this structure:
{
  "items": [
    {
      "name": "Food Name",
      "quantity": "Quantity",
      "calories": number,
      "protein": number,
      "carbs": number,
      "fat": number
    }
  ]
}
"""

        # Prepare the request payload
        request_payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            }
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 1000
        }

        logger.info("Prepared OpenAI API request payload")

        # Call OpenAI API with the image
        try:
            logger.info("Sending request to OpenAI API...")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openai_api_key}",
                        "Content-Type": "application/json"
                    },
                    json=request_payload,
                    timeout=60.0  # Extended timeout for image processing
                )

                logger.info(f"Received response from OpenAI API: status_code={response.status_code}")

                if response.status_code != 200:
                    logger.error(f"OpenAI API error: {response.status_code}")
                    logger.error(f"Response content: {response.text}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Error from vision API: {response.text}"
                    )

                data = response.json()
                logger.info("Successfully parsed JSON response from OpenAI API")

        except httpx.TimeoutException:
            logger.error("Request to OpenAI API timed out")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Vision analysis timed out. Please try again with a simpler image."
            )
        except httpx.RequestError as e:
            logger.error(f"Error making request to OpenAI API: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error connecting to vision service: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during API call: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error during vision API call: {str(e)}"
            )

        # Extract and parse the AI response
        try:
            ai_response = data["choices"][0]["message"]["content"]
            logger.info("Successfully extracted content from API response")
            logger.debug(f"AI response content: {ai_response}")

            # Parse the JSON response
            import json
            response_data = json.loads(ai_response)
            logger.info("Successfully parsed JSON from AI response")

            if "items" not in response_data or not isinstance(response_data["items"], list):
                logger.error(f"Invalid response format: {response_data}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid response format from vision API: 'items' field missing or not a list"
                )

            # Convert to FoodItem objects
            food_items = []
            for i, item in enumerate(response_data["items"]):
                try:
                    logger.debug(f"Processing food item {i+1}: {item}")

                    # Ensure all required fields are present
                    name = item.get("name", "Unknown Food")
                    quantity = item.get("quantity", "1 serving")

                    # Convert numerical fields with error handling
                    try:
                        calories = float(item.get("calories", 0))
                    except (TypeError, ValueError):
                        logger.warning(f"Invalid calories value for item {i+1}: {item.get('calories')}")
                        calories = 0

                    try:
                        protein = float(item.get("protein", 0))
                    except (TypeError, ValueError):
                        logger.warning(f"Invalid protein value for item {i+1}: {item.get('protein')}")
                        protein = 0

                    try:
                        carbs = float(item.get("carbs", 0))
                    except (TypeError, ValueError):
                        logger.warning(f"Invalid carbs value for item {i+1}: {item.get('carbs')}")
                        carbs = 0

                    try:
                        fat = float(item.get("fat", 0))
                    except (TypeError, ValueError):
                        logger.warning(f"Invalid fat value for item {i+1}: {item.get('fat')}")
                        fat = 0

                    # Create FoodItem
                    food_item = FoodItem(
                        name=name,
                        quantity=quantity,
                        calories=calories,
                        protein=protein,
                        carbs=carbs,
                        fat=fat
                    )

                    food_items.append(food_item)
                    logger.info(f"Successfully processed food item: {food_item.name}")

                except Exception as e:
                    logger.warning(f"Error processing food item {i+1}: {str(e)}")
                    # Continue processing other items instead of failing completely

            if not food_items:
                logger.warning("No food items were successfully parsed")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Could not identify any food items in the image"
                )

            logger.info(f"Successfully processed {len(food_items)} food items")
            return ScanResponse(items=food_items)

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            logger.error(f"Raw response that failed parsing: {ai_response}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error parsing response from vision API: {str(e)}"
            )
        except KeyError as e:
            logger.error(f"Missing key in API response: {str(e)}")
            logger.error(f"API response structure: {data}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected response structure from vision API: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Error processing API response: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing API response: {str(e)}"
            )

    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        logger.error(f"Unexpected error in scan_image endpoint: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error analyzing image: {str(e)}"
        )