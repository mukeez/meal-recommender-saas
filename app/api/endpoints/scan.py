"""Scanning endpoints for the meal recommendation API.

This module contains FastAPI routes for scanning barcodes and food images
to retrieve nutritional information.
"""

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Body, Query
import asyncio
import logging
import base64
import json
from typing import Optional
from PIL import Image
import io
import google.generativeai as genai

from app.api.auth_guard import auth_guard
from app.core.config import settings
from app.services.product_service import ProductService
from app.services.openfoodfacts_service import OpenFoodFactsService
from app.services.vector_search.vector_search_service import vector_search_service
from app.services.image_preprocessing_service import ImagePreprocessingService
from app.services.scan_llm_service import scan_llm_service, LLMServiceError
from app.services.food_identification_service import food_identification_service
from app.services.indigenous_judge_service import indigenous_judge_service
from app.utils.constants import calculate_nutrition_for_amount
from app.models.scan import (
    FoodItem,
    SimilarDish,
    IndigenousClassification,
    ScanResponse,
    EnhancedScanResponse,
    ScanToMealRequest,
    ScanToMealResponse
)
import traceback

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
product_service = ProductService()
openfoodfacts_service = OpenFoodFactsService()
image_preprocessing_service = ImagePreprocessingService()


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
        
            merged_nutrition = product.nutrition_facts or product.gpt_nutrition_facts
            if not merged_nutrition:
                raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No nutrition information available for this product"
            )

            food_item = normalize_food_item_data(merged_nutrition.model_dump())
            return ScanResponse(items=[food_item])
            

        # return verified nutrition facts with normalization
        merged_nutrition = product[0].nutrition_facts or product[0].gpt_nutrition_facts
        if not merged_nutrition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No nutrition information available for this product"
            )
        food_item = normalize_food_item_data(merged_nutrition.model_dump())
        logger.info(f"Successfully scanned barcode: {barcode} - Found product: {food_item.name}")
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
    response_model=EnhancedScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze food image with vector search and AI fallback",
    description="Upload a food image and get nutritional information using vector search with Replicate embeddings, falling back to vision AI when needed.",
)
async def scan_image(
    image: UploadFile = File(...), 
    similarity_threshold: float = Query(0.75, ge=0.0, le=1.0, description="Minimum similarity score for vector search"),
    country_filter: Optional[str] = Query(None, description="Filter results by country"),
    max_results: int = Query(3, ge=1, le=10, description="Maximum number of similar dishes to return"),
    user=Depends(auth_guard)
) -> EnhancedScanResponse:
    """Analyze a food image using vector search with Replicate embeddings as primary method.

    This endpoint first attempts to find similar dishes using Replicate embeddings
    and vector search. If no matches are found above the threshold, it falls back
    to LLM-based nutritional analysis.

    Args:
        image: Uploaded food image
        similarity_threshold: Minimum similarity score for vector search (0.0 to 1.0)
        country_filter: Optional country to filter results by
        max_results: Maximum number of similar dishes to return
        user: Authenticated user (from auth_guard dependency)

    Returns:
        Enhanced response with both vector search results and nutritional analysis

    Raises:
        HTTPException: If the image analysis fails
    """
    try:
        logger.info(
            f"Received image scan: filename={image.filename}, "
            f"similarity_threshold={similarity_threshold}, country_filter={country_filter}"
        )

        # Read and validate image
        try:
            contents = await image.read()
            logger.info(f"Successfully read image file, size={len(contents)} bytes")
        except Exception as e:
            logger.error(f"Error reading image file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error reading uploaded file",
            )

        if not contents or len(contents) == 0:
            logger.error("Uploaded file is empty")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Uploaded file is empty"
            )

        # Validate image format
        try:
            img = Image.open(io.BytesIO(contents))
            img_format = img.format
            logger.info(f"Image format detected: {img_format}, size: {img.size}")
        except Exception as e:
            logger.error(f"Error validating image format: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format"
            )

        logger.info("Preprocessing image for better analysis quality")
        try:
            preprocessed_image_bytes = image_preprocessing_service.preprocess_image(contents)
            
            if preprocessed_image_bytes is None:
                logger.warning("Image preprocessing failed, using original image")
                processed_contents = contents
            else:
                logger.info(f"Image preprocessing successful: {len(contents)} -> {len(preprocessed_image_bytes)} bytes")
                processed_contents = preprocessed_image_bytes
                
        except Exception as e:
            logger.warning(f"Image preprocessing error: {str(e)}, using original image")
            processed_contents = contents

        similar_dishes = []
        search_method = "llm_fallback"  # Default fallback
        message = None

        try:
            logger.info("Attempting vector search using Replicate embeddings...")
            
            if country_filter:
                similar_dishes_raw = await vector_search_service.search_similar_dishes_by_country(
                    image_bytes=processed_contents,
                    country=country_filter,
                    similarity_threshold=0.70,  # Use 0.70 threshold
                    match_count=max_results
                )
            else:
                similar_dishes_raw = await vector_search_service.search_similar_dishes(
                    image_bytes=processed_contents,
                    similarity_threshold=0.70,  # Use 0.70 threshold 
                    match_count=max_results
                )



            # Convert to SimilarDish objects
            for dish_data in similar_dishes_raw:
                similar_dish = SimilarDish(
                    id= dish_data.get('id'),
                    dish_name=dish_data.get('dish_name', 'Unknown Dish'),
                    country=dish_data.get('country'),
                    description=dish_data.get('description'),
                    similarity=float(dish_data.get('similarity', 0.0)),
                    calories=dish_data.get("nutritional_info", {}).get("calories"),
                    protein=dish_data.get("nutritional_info", {}).get("protein"),
                    carbs=dish_data.get("nutritional_info", {}).get("carbs"),
                    fat=dish_data.get("nutritional_info", {}).get("fats"),
                    serving_unit=dish_data.get("nutritional_info", {}).get("serving_unit", "grams"),
                    amount=dish_data.get("nutritional_info", {}).get("amount", 100.0)  # Default to 100g
                )
                similar_dishes.append(similar_dish)

            
            if similar_dishes_raw:
                # Sort by similarity score and pick the highest
                similar_dishes.sort(key=lambda x: x.similarity, reverse=True)
                best_match = similar_dishes[0]
                logger.info(f"Best match from vector search: {best_match.dish_name} (similarity: {best_match.similarity:.3f})")

                if best_match.similarity < 0.7:
                    message = "No similar dishes found above 0.70 threshold, using AI nutritional analysis"
            else:
                logger.info("No dishes found via vector search.")
                message = "No similar dishes found, using AI nutritional analysis"
            
        except Exception as e:
            logger.warning(f"Vector search failed: {str(e)}")
            message = "Vector search unavailable, using AI nutritional analysis"

        logger.info("Performing LLM-based nutritional analysis...")
        
        # Encode preprocessed image for LLM (use preprocessed image for better results)
        encoded_image = base64.b64encode(processed_contents).decode("utf-8")
        
        # Check API keys
        openai_api_key = settings.OPENAI_API_KEY
        if not openai_api_key:
            logger.error("OpenAI API key not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing image",
            )
        
        
        logger.info("Starting 3-stage approach: Stage 1 (Vector) completed, running Stage 2 & 3")
        
        # Convert similar_dishes to proper format for indigenous judge
        vector_results_for_judge = []
        for dish in similar_dishes:
            vector_results_for_judge.append({
                'dish_name': dish.dish_name,
                'country': dish.country,
                'description': dish.description,
                'similarity': dish.similarity
            })
        
        food_id_task = asyncio.create_task(
            food_identification_service.identify_food(encoded_image)
        )
        
        
        logger.info("Running indigenous classification for all images to ensure comprehensive coverage")
        # Get food_id result first, then run indigenous judge
        food_identification_result = await food_id_task
        
        indigenous_classification = await indigenous_judge_service.judge_indigenous_classification(
            encoded_image=encoded_image,
            vector_search_results=vector_results_for_judge,
            food_identification=food_identification_result
        )
        
        # Now create a focused nutritional analysis prompt based on our 3-stage results
        logger.info("Creating focused nutritional analysis prompt using 3-stage results...")
        
        # Build context from our 3-stage analysis
        analysis_context = ""
        
        # Add vector search context if available
        if similar_dishes and similar_dishes[0].similarity >= 0.8:
            best_match = similar_dishes[0]
            analysis_context += f"HIGH CONFIDENCE VECTOR MATCH: {best_match.dish_name} (similarity: {best_match.similarity:.2f})\n"
            analysis_context += f"Country: {best_match.country or 'Unknown'}\n"
            if best_match.description:
                analysis_context += f"Description: {best_match.description}\n"
        elif similar_dishes:
            analysis_context += f"VECTOR MATCHES FOUND: {', '.join([d.dish_name for d in similar_dishes[:2]])} but lower confidence\n"
        else:
            analysis_context += "NO VECTOR MATCHES FOUND\n"
        
        # Add food identification context
        analysis_context += f"\nFOOD IDENTIFICATION: {food_identification_result.get('identified_food', 'Unknown')}\n"
        analysis_context += f"Category: {food_identification_result.get('food_category', 'Unknown')}\n"
        analysis_context += f"Visible Ingredients: {', '.join(food_identification_result.get('visible_ingredients', []))}\n"
        
        # Add indigenous classification context if available
        if indigenous_classification:
            analysis_context += f"\nINDIGENOUS CLASSIFICATION: {'Yes' if indigenous_classification.get('is_indigenous') else 'No'}\n"
            analysis_context += f"Confidence: {indigenous_classification.get('confidence', 0):.2f}\n"
            if indigenous_classification.get('country_of_origin'):
                analysis_context += f"Origin: {indigenous_classification.get('country_of_origin')}\n"
        
        # Determine the authoritative dish name based on our 3-stage analysis
        authoritative_dish_name = None
        
        # Indigenous classification has final authority over naming
        if indigenous_classification:
            if indigenous_classification.get("is_indigenous"):
                # If confirmed indigenous, prioritize vector match if high confidence
                if similar_dishes and similar_dishes[0].similarity >= 0.8:
                    authoritative_dish_name = similar_dishes[0].dish_name
                    logger.info(f"Indigenous dish confirmed - using vector match name: {authoritative_dish_name}")
                elif food_identification_result.get('identified_food') and food_identification_result.get('identified_food') != 'Unknown':
                    authoritative_dish_name = food_identification_result.get('identified_food')
                    logger.info(f"Indigenous dish confirmed - using food identification name: {authoritative_dish_name}")
            else:
                # If NOT indigenous, always use neutral food identification (ignore vector matches)
                if food_identification_result.get('identified_food') and food_identification_result.get('identified_food') != 'Unknown':
                    authoritative_dish_name = food_identification_result.get('identified_food')
                    logger.info(f"NON-indigenous dish confirmed - using neutral food ID name: {authoritative_dish_name}")
                else:
                    authoritative_dish_name = "Unknown Food"
                    logger.info("NON-indigenous dish confirmed but no food ID available")
        else:
            # No indigenous classification - use original priority system
            # Priority 1: High confidence vector match
            if similar_dishes and similar_dishes[0].similarity >= 0.8:
                authoritative_dish_name = similar_dishes[0].dish_name
                logger.info(f"Using vector match name: {authoritative_dish_name}")
            # Priority 2: Food identification service result  
            elif food_identification_result.get('identified_food') and food_identification_result.get('identified_food') != 'Unknown':
                authoritative_dish_name = food_identification_result.get('identified_food')
                logger.info(f"Using food identification name: {authoritative_dish_name}")
        
        # Create a focused nutritional analysis prompt
        prompt = f"""You are a nutrition expert. Analyze this food image and provide nutritional information.

CONTEXT FROM ANALYSIS:
{analysis_context}

IMPORTANT NAMING INSTRUCTION:
- The dish has been expertly identified as: "{authoritative_dish_name or 'Unknown Food'}"
- You MUST use this exact name in your response
- Do NOT create your own dish name or add cultural specificity unless confirmed by expert analysis
- Focus ONLY on nutritional analysis, not dish identification

Based on the image and the analysis context above, provide nutritional information for the complete serving shown:

Requirements:
1. Use the EXACT dish name provided above: "{authoritative_dish_name or 'Unknown Food'}"
2. Use the analysis context to inform your nutritional estimates
3. If there's a high confidence vector match, use it as a baseline but adjust for what you see
4. Focus on the actual serving size visible in the image
5. Detect all visible ingredients in the meal

Provide your analysis in this exact JSON format:
{{
  "items": [
    {{
      "name": "{authoritative_dish_name or 'Unknown Food'}",
      "amount": estimated_weight_in_grams,
      "serving_unit": "grams",
      "calories": total_calories_for_serving,
      "protein": total_protein_in_grams,
      "carbs": total_carbs_in_grams,
      "fat": total_fat_in_grams
    }}
  ],
  "detected_ingredients": ["ingredient1", "ingredient2", "ingredient3"]
}}

CRITICAL: Use the exact dish name "{authoritative_dish_name or 'Unknown Food'}" - do not modify it or add cultural context unless the expert analysis confirmed it as indigenous."""

        try:
            logger.info("Sending focused nutritional analysis request...")
            response_data = await scan_llm_service.analyze_image(
                encoded_image=encoded_image,
                prompt=prompt
            )
            logger.info("Successfully received nutritional analysis response")

        except LLMServiceError as e:
            logger.error(f"LLM service error: {e}")
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Vision analysis timed out. Please try again with a simpler image.",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

        # Extract and parse the AI response
        try:
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

            # Extract detected ingredients from the response
            detected_ingredients = response_data.get("detected_ingredients", [])
            if not isinstance(detected_ingredients, list):
                logger.warning(f"Invalid detected_ingredients format: {detected_ingredients}")
                detected_ingredients = []
            
            logger.info(f"Successfully processed {len(food_items)} food items")
            logger.info(f"Detected {len(detected_ingredients)} ingredients: {detected_ingredients}")
            
            # Determine search method based on what was used
            if similar_dishes and similar_dishes[0].similarity >= 0.7:
                search_method = "both"  # Vector search + LLM refinement
            elif similar_dishes:
                search_method = "llm_fallback"  # LLM with vector context
            else:
                search_method = "llm_fallback"  # Pure LLM analysis
            
            # Generate confidence explanation based on 3-stage results
            confidence_explanation = ""
            if similar_dishes and similar_dishes[0].similarity >= 0.8:
                confidence_explanation = f"High confidence vector match found for {similar_dishes[0].dish_name} ({similar_dishes[0].similarity:.1%} similarity). Used 3-stage analysis with vector foundation."
            elif similar_dishes:
                confidence_explanation = f"Vector matches found but with moderate confidence. Used 3-stage analysis for comprehensive evaluation."
            else:
                confidence_explanation = "No vector matches found. Used 3-stage analysis with neutral food identification and indigenous classification."
            
            # Add indigenous classification context to explanation
            if indigenous_classification:
                if indigenous_classification.get("is_indigenous"):
                    confidence_explanation += f" Indigenous classification: {indigenous_classification.get('country_of_origin', 'Traditional')} dish identified."
                else:
                    confidence_explanation += " Non-indigenous dish confirmed through expert analysis."
            
            # Prepare indigenous classification for response
            indigenous_classification_response = None
            if indigenous_classification:
                indigenous_classification_response = IndigenousClassification(
                    is_indigenous=indigenous_classification.get("is_indigenous", False),
                    confidence=indigenous_classification.get("confidence", 0.0),
                    country_of_origin=indigenous_classification.get("country_of_origin"),
                    dish_classification=indigenous_classification.get("dish_classification", "Unknown"),
                    reasoning=indigenous_classification.get("reasoning", "No classification performed")
                )
                
                logger.info(f"Indigenous classification result: {indigenous_classification_response.is_indigenous} "
                           f"({indigenous_classification_response.confidence:.2f} confidence)")
            
            # Return enhanced response with both vector search and LLM results
            return EnhancedScanResponse(
                items=food_items,
                similar_dishes=similar_dishes,
                detected_ingredients=detected_ingredients,
                search_method=search_method,
                message=message or f"Successfully analyzed image using {search_method}",
                confidence_explanation=confidence_explanation,
                indigenous_classification=indigenous_classification_response
            )

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            logger.error(f"Raw response that failed parsing: {response_data}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error parsing response from vision API",
            )
        except KeyError as e:
            logger.error(f"Missing key in API response: {str(e)}")
            logger.error(f"API response structure: {response_data}")
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
        HTTPException: If conversion fails
    """
    try:
        logger.info(f"Converting scan data to meal format for amount: {request.desired_amount}g")
        
        # Calculate nutrition for the desired amount
        calories, protein, carbs, fat = calculate_nutrition_for_amount(
            request.food_item.calories_per_gram,
            request.food_item.protein_per_gram,
            request.food_item.carbs_per_gram,
            request.food_item.fat_per_gram,
            request.desired_amount
        )
        
        return ScanToMealResponse(
            name=request.food_item.name,
            calories=calories,
            protein=protein,
            carbs=carbs,
            fat=fat,
            serving_unit="grams",
            amount=request.desired_amount,
            notes=request.notes,
            favorite=request.favorite,
            logging_mode="scanned"
        )
        
    except Exception as e:
        logger.error(f"Error converting scan to meal: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error converting scan data to meal format"
        )


def normalize_food_item_data(nutrition_facts: dict) -> FoodItem:
    """Normalize food item data from various sources to a consistent FoodItem model.

    This function takes raw nutrition facts from different sources (e.g., Nutritionix, OpenFoodFacts)
    and normalizes the data to match the FoodItem model used in the application.

    Args:
        nutrition_facts: The raw nutrition facts data as a dictionary

    Returns:
        A normalized FoodItem instance

    Raises:
        ValueError: If required fields are missing or invalid
    """
    try:
        # Extract and convert fields with error handling
        name = nutrition_facts.get("name", "Unknown Food")
        
        # Handle both new format (amount + serving_unit) and old format (quantity) for backwards compatibility
        amount = nutrition_facts.get("amount")
        serving_unit = nutrition_facts.get("serving_unit", "grams")
        quantity = nutrition_facts.get("quantity")  # Fallback for old format

        # Convert numerical fields with error handling
        try:
            calories = float(nutrition_facts.get("calories", 0))
        except (TypeError, ValueError):
            logger.warning(f"Invalid calories value: {nutrition_facts.get('calories')}")
            calories = 0

        try:
            protein = float(nutrition_facts.get("protein", 0))
        except (TypeError, ValueError):
            logger.warning(f"Invalid protein value: {nutrition_facts.get('protein')}")
            protein = 0

        try:
            carbs = float(nutrition_facts.get("carbs", 0))
        except (TypeError, ValueError):
            logger.warning(f"Invalid carbs value: {nutrition_facts.get('carbs')}")
            carbs = 0

        try:
            fat = float(nutrition_facts.get("fat", 0))
        except (TypeError, ValueError):
            logger.warning(f"Invalid fat value: {nutrition_facts.get('fat')}")
            fat = 0

        # Create FoodItem instance
        food_item = FoodItem(
            name=name,
            amount=amount if amount is not None else 100.0,  # Default to 100g if not provided
            serving_unit=serving_unit,
            calories=calories,
            protein=protein,
            carbs=carbs,
            fat=fat,
            calories_per_gram=calories / (amount if amount > 0 else 1),
            protein_per_gram=protein / (amount if amount > 0 else 1),
            carbs_per_gram=carbs / (amount if amount > 0 else 1),
            fat_per_gram=fat / (amount if amount > 0 else 1),
        )

        logger.info(f"Normalized food item: {food_item.name}, amount: {food_item.amount}{food_item.serving_unit}, "
                    f"calories: {food_item.calories}, protein: {food_item.protein}, "
                    f"carbs: {food_item.carbs}, fat: {food_item.fat}")

        return food_item

    except Exception as e:
        logger.error(f"Error normalizing food item data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error normalizing food item data"
        )