"""Base class for AI services"""

from typing import Any
import openai
import json
import logging
from app.core.config import settings
from openai import OpenAI
import google.generativeai as genai

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Custom exception for AI service errors."""

    pass


class BaseLLMService:
    """
    Base class for AI services.

    Provides template methods for generating response from AI while allowing subclasses to override or extend any part as needed.
    """

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.MODEL_NAME
        
        # Initialize Gemini client if API key is available
        self.gemini_client = None
        if settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self.gemini_client = genai.GenerativeModel('gemini-2.0-flash-exp')
        else:
            logger.warning("Gemini API key not configured, fallback unavailable")

    def _build_prompt(self, request: Any) -> str:
        """
        Construct the prompt string. Subclasses should override this.
        """
        raise NotImplementedError("Subclasses must implement _build_prompt")

    def _parse_response(self, content: str) -> Any:
        """
        Parse raw AI output into structured objects. Subclasses should override this.
        """
        raise NotImplementedError("Subclasses must implement _parse_response")

    async def _send_gemini_request(
        self,
        system_prompt: str,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a request to Gemini API as fallback.
        
        Args:
            system_prompt: The system prompt to set the context
            prompt: The user input to generate a response for
            max_tokens: Maximum number of tokens in the response  
            temperature: Sampling temperature for response variability
            
        Returns:
            The raw response content from Gemini
            
        Raises:
            LLMServiceError: If Gemini API fails
        """
        if not self.gemini_client:
            raise LLMServiceError("Gemini client not initialized")
        
        try:
            # Combine system prompt and user prompt for Gemini
            combined_prompt = f"{system_prompt}\n\nUser Request: {prompt}"
            
            # Configure generation settings
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            
            # Generate response
            response = self.gemini_client.generate_content(
                combined_prompt,
                generation_config=generation_config
            )
            
            logger.info("Successfully received response from Gemini API")
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise LLMServiceError(f"Gemini API error: {e}")

    async def _send_request(
        self,
        system_prompt,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """
        Send a request to the AI service with Gemini fallback on server errors.
        Args:
            system_prompt: The system prompt to set the context for the AI.
            prompt: The user input to generate a response for.
            max_tokens: Maximum number of tokens in the response.
            temperature: Sampling temperature for response variability.
        Returns:
            The raw response content from the AI service.
        """
        try:
            logger.info("Sending request to OpenAI API...")
            response = self.client.chat.completions.create(
                model=settings.MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
                temperature=temperature,
            )
            logger.info("Successfully received response from OpenAI API")
            return response.choices[0].message.content
            
        except openai.OpenAIError as openai_error:
            # Check if it's a server error (5xx) or rate limit that should trigger fallback
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
                logger.info("Attempting Gemini fallback...")
                try:
                    # Use Gemini as fallback 
                    gemini_response = await self._send_gemini_request(
                        system_prompt=system_prompt,
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    logger.info("Successfully received response from Gemini fallback")
                    return gemini_response
                    
                except Exception as gemini_error:
                    logger.error(f"Gemini fallback also failed: {gemini_error}")
                    # Return original OpenAI error since it was the primary service
                    raise LLMServiceError(f"OpenAI API error: {openai_error} (Gemini fallback also failed: {gemini_error})")
            
            # If no fallback or non-server error, raise original error
            logger.error(f"OpenAI API error (no fallback attempted): {openai_error}")
            raise LLMServiceError(f"OpenAI API error: {openai_error}")

    async def generate_response(
        self,
        system_prompt: str,
        request: Any,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        **kwargs
    ) -> Any:
        """
        Template method: build prompt, send request, parse response.

        Args:
            request: Any
        Returns:
            A parsed response generated by the AI service
        """
        should_parse = kwargs.get("should_parse", True) 

        prompt = self._build_prompt(request)
        raw = await self._send_request(
            system_prompt=system_prompt,
            prompt=prompt,
            # max_tokens=max_tokens,
            temperature=temperature,
        )
        if not should_parse:
            return raw
        return self._parse_response(raw)
