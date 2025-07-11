"""Scanning endpoints for the meal recommendation API.

This module contains FastAPI routes for scanning barcodes and food images
to retrieve nutritional information.
"""

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Body
import httpx
import logging
import base64
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from PIL import Image
import io
import google.generativeai as genai

from app.api.auth_guard import auth_guard
from app.core.config import settings
from app.services.product_service import product_service
from app.services.openfoodfacts_service import openfoodfacts_service
from app.utils.constants import parse_gram_quantity, normalize_nutrition_to_per_gram, calculate_nutrition_for_amount
import traceback

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


# Models
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


def normalize_food_item_data(nutrition_facts: dict) -> FoodItem:
    """Normalize nutrition facts data to consistent per-gram format.
    
    Args:
        nutrition_facts: Dictionary containing nutrition data in either old format (with quantity) 
                        or new format (with amount and serving_unit)
        
    Returns:
        FoodItem with normalized data and per-gram values
    """
    # Handle both old format (quantity) and new format (amount + serving_unit)
    if "amount" in nutrition_facts and "serving_unit" in nutrition_facts:
        # New format - amount is already numeric
        gram_amount = float(nutrition_facts["amount"])
        serving_unit = nutrition_facts.get("serving_unit", "grams")
    elif "quantity" in nutrition_facts:
        # Old format - parse quantity string to get gram amount
        quantity_str = nutrition_facts.get("quantity", "100g")
        gram_amount = parse_gram_quantity(quantity_str)
        serving_unit = "grams"
    else:
        # Fallback
        gram_amount = 100.0
        serving_unit = "grams"
    
    # Get nutrition values for the specified amount
    calories = float(nutrition_facts.get("calories", 0))
    protein = float(nutrition_facts.get("protein", 0))
    carbs = float(nutrition_facts.get("carbs", 0))
    fat = float(nutrition_facts.get("fat", 0))
    
    # Calculate per-gram values
    calories_per_gram, protein_per_gram, carbs_per_gram, fat_per_gram = normalize_nutrition_to_per_gram(
        calories, protein, carbs, fat, gram_amount
    )
    
    return FoodItem(
        name=nutrition_facts.get("name", "Unknown Food"),
        amount=gram_amount,
        serving_unit=serving_unit,
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat,
        calories_per_gram=calories_per_gram,
        protein_per_gram=protein_per_gram,
        carbs_per_gram=carbs_per_gram,
        fat_per_gram=fat_per_gram
    )


class ScanResponse(BaseModel):
    """Response model for scan endpoints.

    Attributes:
        items: List of food items with nutritional information
    """

    items: List[FoodItem]


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


@router.post(
    "/barcode",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Scan barcode for nutritional information",
    description="Scan a UPC barcode and retrieve nutritional information using Nutritionix API.",
)
async def scan_barcode(
    barcode: str = Body(..., embed=True), user=Depends(auth_guard)
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
                detail="Invalid barcode format. Barcode must contain only digits.",
            )

        product = await product_service.scan_barcode(barcode=barcode)
        if not product:
            # get product info from openfoodfacts
            product = await openfoodfacts_service.scan_barcode(barcode=barcode)
            # insert product into database
            await product_service.log_product(product)
            # return ai generated nutrition facts with normalization
            if product.gpt_nutrition_facts is not None:
                food_item = normalize_food_item_data(product.gpt_nutrition_facts.model_dump())
                return ScanResponse(items=[food_item])
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No nutrition information available for this product"
                )

        # return verified nutrition facts with normalization
        if product[0].nutrition_facts is not None:
            food_item = normalize_food_item_data(product[0].nutrition_facts.model_dump())
        elif product[0].gpt_nutrition_facts is not None:
            food_item = normalize_food_item_data(product[0].gpt_nutrition_facts.model_dump())
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No nutrition information available for this product"
            )
        return ScanResponse(items=[food_item])

    except HTTPException:
        # Re-raise HTTP exceptions without modification
        traceback.print_exc()
        raise
    except Exception as e:
        logger.error(f"Unexpected error scanning barcode: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing barcode",
        )


async def call_gemini_vision(encoded_image: str, prompt: str) -> dict:
    """Call Gemini Vision API as fallback for food image analysis.
    
    Args:
        encoded_image: Base64 encoded image
        prompt: The analysis prompt
        
    Returns:
        Parsed JSON response from Gemini
        
    Raises:
        HTTPException: If Gemini API fails
    """
    try:
        gemini_api_key = settings.GEMINI_API_KEY
        if not gemini_api_key:
            logger.warning("Gemini API key not configured, skipping fallback")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No fallback vision service available"
            )
        
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Decode base64 image
        import base64
        image_bytes = base64.b64decode(encoded_image)
        
        # Create image part for Gemini
        from PIL import Image
        import io
        image = Image.open(io.BytesIO(image_bytes))
        
        # Generate response
        response = model.generate_content([prompt, image])
        
        # Parse JSON response
        response_data = json.loads(response.text)
        
        logger.info("Successfully received response from Gemini Vision API")
        return response_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Gemini JSON parse error: {str(e)}")
        logger.error(f"Raw Gemini response: {response.text}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error parsing Gemini API response"
        )
    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gemini vision analysis failed"
        )


@router.post(
    "/image",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze food image for nutritional information",
    description="Upload a food image and get nutritional information using vision AI.",
)
async def scan_image(
    image: UploadFile = File(...), user=Depends(auth_guard)
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
        logger.info(
            f"Received image upload: filename={image.filename}, content_type={image.content_type}"
        )

        try:
            contents = await image.read()
            logger.info(f"Successfully read image file, size={len(contents)} bytes")
        except Exception as e:
            logger.error(f"Error reading image file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error reading uploaded file",
            )

        if not contents or len(contents) == 0:
            logger.error("Uploaded file is empty")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty"
            )

        try:

            img = Image.open(io.BytesIO(contents))
            img_format = img.format
            logger.info(f"Image format detected: {img_format}, size: {img.size}")
        except Exception as e:
            logger.error(f"Error validating image format: {str(e)}")
            logger.error("This may not be a valid image file")

        try:
            encoded_image = base64.b64encode(contents).decode("utf-8")
            logger.info(
                f"Successfully base64 encoded image, encoded_size={len(encoded_image)}"
            )
        except Exception as e:
            logger.error(f"Error encoding image to base64: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing image",
            )

        openai_api_key = settings.OPENAI_API_KEY
        if not openai_api_key:
            logger.error("OpenAI API key not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing image",
            )

        model_name = "gpt-4o-mini"
        logger.info(f"Using vision model: {model_name}")

        prompt = """Identify this image as a complete meal or dish. Do not break it down into individual components.

Provide a single, descriptive name for the entire meal as it appears in the image. If there are multiple components, describe them as one unified dish (e.g., "Jollof rice with grilled chicken and plantains" rather than separate items).

For the complete meal shown, provide:
1. Descriptive name of the entire meal/dish (be as descriptive as possible)
2. Estimated total weight of the entire serving shown (as a numeric value in grams)
3. Serving unit (Always use "grams")  
4. Total estimated calories for the entire serving shown
5. Total estimated protein for the entire serving shown
6. Total estimated carbs for the entire serving shown
7. Total estimated fat for the entire serving shown

IMPORTANT: Treat this as ONE complete meal. All nutritional values should be for the entire serving visible in the image.

Format your response as a valid JSON object with this structure:
{
  "items": [
    {
      "name": "Complete descriptive meal name",
      "amount": number,
      "serving_unit": "grams", 
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
                            },
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 1000,
        }

        logger.info("Prepared OpenAI API request payload")

        # Call OpenAI API with the image (primary), fallback to Gemini if it fails
        try:
            logger.info("Sending request to OpenAI API...")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_payload,
                    timeout=60.0,  # Extended timeout for image processing
                )

                logger.info(
                    f"Received response from OpenAI API: status_code={response.status_code}"
                )

                if response.status_code != 200:
                    logger.error(f"OpenAI API error: {response.status_code}")
                    logger.error(f"Response content: {response.text}")
                    raise Exception(f"OpenAI API returned status {response.status_code}")

                data = response.json()
                logger.info("Successfully parsed JSON response from OpenAI API")

        except Exception as openai_error:
            logger.warning(f"OpenAI Vision failed: {str(openai_error)}")
            logger.info("Trying Gemini Vision as fallback...")
            
            try:
                # Try Gemini as fallback
                response_data = await call_gemini_vision(encoded_image, prompt)
                # Skip to processing since we have the response data directly
                data = {"choices": [{"message": {"content": json.dumps(response_data)}}]}
                logger.info("Successfully received response from Gemini fallback")
                
            except Exception as gemini_error:
                logger.error(f"Both OpenAI and Gemini failed. OpenAI: {str(openai_error)}, Gemini: {str(gemini_error)}")
                
                # Return appropriate error based on the primary failure
                if "timed out" in str(openai_error).lower() or "timeout" in str(openai_error).lower():
                    raise HTTPException(
                        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                        detail="Vision analysis timed out. Please try again with a simpler image.",
                    )
                elif "connect" in str(openai_error).lower() or "network" in str(openai_error).lower():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Error connecting to vision service",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Vision analysis failed",
                    )

        # Extract and parse the AI response
        try:
            ai_response = data["choices"][0]["message"]["content"]
            logger.info("Successfully extracted content from API response")
            logger.debug(f"AI response content: {ai_response}")

            # Parse the JSON response

            response_data = json.loads(ai_response)
            logger.info("Successfully parsed JSON from AI response")

            if "items" not in response_data or not isinstance(
                response_data["items"], list
            ):
                logger.error(f"Invalid response format: {response_data}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid response format from vision API: 'items' field missing or not a list",
                )

            # Convert to FoodItem objects
            food_items = []
            for i, item in enumerate(response_data["items"]):
                try:
                    logger.debug(f"Processing food item {i+1}: {item}")

                    # Ensure all required fields are present
                    name = item.get("name", "Unknown Food")
                    
                    # Handle both new format (amount + serving_unit) and old format (quantity) for backwards compatibility
                    amount = item.get("amount")
                    serving_unit = item.get("serving_unit", "grams")
                    quantity = item.get("quantity")  # Fallback for old format

                    # Convert numerical fields with error handling
                    try:
                        calories = float(item.get("calories", 0))
                    except (TypeError, ValueError):
                        logger.warning(
                            f"Invalid calories value for item {i+1}: {item.get('calories')}"
                        )
                        calories = 0

                    try:
                        protein = float(item.get("protein", 0))
                    except (TypeError, ValueError):
                        logger.warning(
                            f"Invalid protein value for item {i+1}: {item.get('protein')}"
                        )
                        protein = 0

                    try:
                        carbs = float(item.get("carbs", 0))
                    except (TypeError, ValueError):
                        logger.warning(
                            f"Invalid carbs value for item {i+1}: {item.get('carbs')}"
                        )
                        carbs = 0

                    try:
                        fat = float(item.get("fat", 0))
                    except (TypeError, ValueError):
                        logger.warning(
                            f"Invalid fat value for item {i+1}: {item.get('fat')}"
                        )
                        fat = 0

                    # Create nutrition data dict for normalization
                    nutrition_data = {
                        "name": name,
                        "calories": calories,
                        "protein": protein,
                        "carbs": carbs,
                        "fat": fat,
                    }
                    
                    # Add the appropriate quantity/amount fields
                    if amount is not None and serving_unit:
                        # New format with amount and serving_unit
                        nutrition_data["amount"] = float(amount)
                        nutrition_data["serving_unit"] = serving_unit
                    elif quantity:
                        # Old format with quantity string
                        nutrition_data["quantity"] = quantity
                    else:
                        # Fallback
                        nutrition_data["amount"] = 100.0
                        nutrition_data["serving_unit"] = "grams"
                    food_item = normalize_food_item_data(nutrition_data)

                    food_items.append(food_item)
                    logger.info(f"Successfully processed food item: {food_item.name}")

                except Exception as e:
                    logger.warning(f"Error processing food item {i+1}: {str(e)}")
                    # Continue processing other items instead of failing completely

            if not food_items:
                logger.warning("No food items were successfully parsed")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Could not identify any food items in the image",
                )

            logger.info(f"Successfully processed {len(food_items)} food items")
            return ScanResponse(items=food_items)

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            logger.error(f"Raw response that failed parsing: {ai_response}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error parsing response from vision API",
            )
        except KeyError as e:
            logger.error(f"Missing key in API response: {str(e)}")
            logger.error(f"API response structure: {data}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected response structure from vision API: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Error processing API response: {str(e)}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing API response",
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
            detail=f"Unexpected error analyzing image",
        )


@router.post(
    "/convert-to-meal",
    response_model=ScanToMealResponse,
    status_code=status.HTTP_200_OK,
    summary="Convert scan data to meal logging format",
    description="Convert scanned food item data to the format needed for meal logging, calculating nutrition for desired amount.",
)
async def convert_scan_to_meal(
    request: ScanToMealRequest,
    user=Depends(auth_guard)
) -> ScanToMealResponse:
    """Convert scanned food item data to meal logging format.
    
    This endpoint takes scanned food data and a desired amount, then calculates
    the nutritional values for that amount and returns data in the format
    needed for the meal logging endpoint.

    Args:
        request: The conversion request with food item and desired amount
        user: Authenticated user (from auth_guard dependency)

    Returns:
        Meal data formatted for logging with calculated nutrition values

    Raises:
        HTTPException: If there is an error processing the conversion
    """
    try:
        # Calculate nutrition for the desired amount
        total_calories, total_protein, total_carbs, total_fat = calculate_nutrition_for_amount(
            request.food_item.calories_per_gram,
            request.food_item.protein_per_gram,
            request.food_item.carbs_per_gram,
            request.food_item.fat_per_gram,
            request.desired_amount
        )

        return ScanToMealResponse(
            name=request.food_item.name,
            calories=round(total_calories, 1),
            protein=round(total_protein, 2),
            carbs=round(total_carbs, 2),
            fat=round(total_fat, 2),
            serving_unit="grams",
            amount=request.desired_amount,
            notes=request.notes,
            favorite=request.favorite,
            logging_mode="scanned"
        )

    except Exception as e:
        logger.error(f"Error converting scan data to meal format: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error converting scan data: {str(e)}",
        )
