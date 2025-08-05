"""AI service for generating recipe suggestions.

This module provides functions to interact with an LLM service
to generate recipe suggestions based on user requirements.
"""
import logging
import json
from typing import Optional, List, Dict, Any
import openai

from app.core.config import settings
from app.models.meal import RecipeSuggestionRequest, RecipeSuggestionResponse
from app.services.base_llm_service import BaseLLMService, LLMServiceError
import traceback

logger = logging.getLogger(__name__)

class RecipeLLMService(BaseLLMService):
    """AI service for generating recipe suggestions based on user requirements."""

    def __init__(self, request: RecipeSuggestionRequest):
        """Initialize the RecipeLLMService with a recipe suggestion request.
        Args:
            request: The recipe suggestion request containing user preferences
        """
        self.request = request
        super().__init__()

    async def _send_request(
        self, system_prompt, prompt, max_tokens=2000, temperature=0.5
    ):
        """
        Send a request to the AI service with Gemini fallback for recipe suggestions.
        Args:
            system_prompt: The system prompt to set the context for the AI.
            prompt: The user input to generate a response for.
            max_tokens: Maximum number of tokens in the response.
            temperature: Sampling temperature for response variability.
        Returns:
            The parsed response from the AI service.
        """
        try:
            logger.info("Sending structured request to OpenAI API for recipes...")
            response = self.client.responses.parse(
                    model=settings.MODEL_NAME,
                    input=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {"role": "user", "content": prompt},
                    ],
                    text_format=RecipeSuggestionResponse)
            logger.info("Successfully received structured response from OpenAI API for recipes")
            return response.output_parsed
            
        except openai.OpenAIError as openai_error:
            should_fallback = False
            error_str = str(openai_error).lower()
            
            if any(keyword in error_str for keyword in [
                'server error', '500', '502', '503', '504', '429', 
                'service unavailable', 'internal server error', 
                'rate limit', 'overloaded'
            ]):
                should_fallback = True
                logger.warning(f"OpenAI server error detected: {openai_error}")
            
            if should_fallback and self.gemini_client:
                logger.info("Attempting Gemini fallback for recipe suggestions...")
                try:
                    gemini_response = await self._send_gemini_request(
                        system_prompt=system_prompt,
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    
                    import json
                    gemini_data = json.loads(gemini_response)
                    parsed_response = RecipeSuggestionResponse(**gemini_data)
                    
                    logger.info("Successfully received and parsed response from Gemini fallback for recipes")
                    return parsed_response
                    
                except Exception as gemini_error:
                    logger.error(f"Gemini fallback for recipes also failed: {gemini_error}")
                    raise LLMServiceError(f"OpenAI API error: {openai_error} (Gemini fallback also failed: {gemini_error})")
            
            logger.error(f"OpenAI API error (no fallback attempted for recipes): {openai_error}")
            raise LLMServiceError(f"OpenAI API error: {openai_error}")

    async def get_recipe_suggestions(self) -> RecipeSuggestionResponse:
        """Get recipe suggestions from OpenAI API.

        Returns:
            A response object containing a list of recipe suggestions.

        Raises:
            LLMServiceError: If there is an error communicating with the API
                            or processing the response.
        """
        try:
            system_prompt = "You are a helpful assistant that suggests recipes based on user's dietary needs."
            
            suggestions = await self.generate_response(
                system_prompt=system_prompt, request=self.request, temperature=0.5, should_parse=False
            )
            return suggestions
        except openai.OpenAIError as e:
            raise LLMServiceError(f"OpenAI API error: {str(e)}")
        except json.JSONDecodeError:
            raise LLMServiceError("Failed to parse AI response as JSON")
        except Exception as e:
            raise LLMServiceError(f"Unexpected error: {str(e)}")

    def _build_prompt(self, request: RecipeSuggestionRequest) -> str:
        """Build a prompt for the OpenAI API.
        
        Args:
            request: The recipe suggestion request
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""Please suggest 5 recipes based on the following criteria:
        - Target Calories: {request.calories} kcal
        - Target Protein: {request.protein} g
        - Target Carbs: {request.carbs} g
        - Target Fat: {request.fat} g
        """

        if request.dietary_preference:
            prompt += f"- Dietary Preference: {request.dietary_preference}\n"

        if request.dietary_restrictions:
            prompt += f"- Dietary Restrictions: {', '.join(request.dietary_restrictions)}\n"

        prompt += """
        For each recipe, provide:
        1.  The name of the dish.
        2.  A brief description.
        3.  A list of ingredients.
        4.  The step-by-step recipe.
        5.  A macronutrient breakdown (protein, carbs, fat, calories).

        Format the response as a JSON object with a "suggestions" property containing an array of recipe objects.
        """
        return prompt

recipe_llm_service = RecipeLLMService
