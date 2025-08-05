"""AI service for analyzing food images.

This module provides the ScanLLMService for interacting with vision models
to analyze food images and extract nutritional information.
"""
import logging
import json
import openai
import base64

from app.core.config import settings
from app.services.base_llm_service import BaseLLMService, LLMServiceError

logger = logging.getLogger(__name__)

class ScanLLMService(BaseLLMService):
    """AI service for analyzing food images."""

    async def analyze_image(self, encoded_image: str, prompt: str) -> dict:
        """
        Analyze a food image using a vision model.

        Args:
            encoded_image: Base64 encoded image string.
            prompt: The prompt to send to the vision model.

        Returns:
            The JSON response from the AI service.
        """
        model_name = "gpt-4o-mini"
        logger.info(f"Using vision model: {model_name}")

        try:
            logger.info("Sending request to OpenAI Vision API...")
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
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
                response_format={"type": "json_object"},
                max_tokens=1000,
            )
            
            ai_response = response.choices[0].message.content
            logger.info("Successfully received response from OpenAI Vision API")
            return json.loads(ai_response)

        except openai.OpenAIError as openai_error:
            logger.warning(f"OpenAI Vision failed: {openai_error}")
            logger.info("Trying Gemini Vision as fallback...")
            
            try:
                if not self.gemini_client:
                    raise LLMServiceError("Gemini client not available for fallback.")
                
                # Gemini requires a different format (PIL image)
                image_bytes = base64.b64decode(encoded_image)
                
                from PIL import Image
                import io
                image = Image.open(io.BytesIO(image_bytes))

                gemini_response = self.gemini_client.generate_content([prompt, image])
                
                response_data = json.loads(gemini_response.text)
                logger.info("Successfully received response from Gemini fallback")
                return response_data

            except Exception as gemini_error:
                logger.error(f"Both OpenAI and Gemini failed. OpenAI: {str(openai_error)}, Gemini: {str(gemini_error)}")
                raise LLMServiceError(f"Vision analysis failed. Primary: {openai_error}, Fallback: {gemini_error}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            raise LLMServiceError("Failed to parse AI response as JSON")
        
        except Exception as e:
            logger.error(f"An unexpected error occurred during image analysis: {e}")
            raise LLMServiceError(f"An unexpected error occurred: {e}")

scan_llm_service = ScanLLMService()
