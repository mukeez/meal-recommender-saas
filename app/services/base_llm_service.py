"""Base class for AI services"""

from typing import Any
import json
import logging
from app.core.config import settings
from litellm import Router
import litellm
import os

logger = logging.getLogger(__name__)

# Helicone integration
if settings.HELICONE_API_KEY:
    litellm.api_base = "https://oai.hconeai.com/v1"
    litellm.metadata = {
    "Helicone-Auth": f"Bearer {settings.HELICONE_API_KEY}",  # Authenticate to send requests to Helicone API
    "Helicone-Cache-Enabled": "true",  # Enable caching of responses
    "Cache-Control": "max-age=3600",  # Set cache limit to 1 hour
    "Helicone-RateLimit-Policy": "100;w=3600;s=user",  # Set rate limit policy
    }
    litellm.success_callback = ["helicone"]

    logger.info("Helicone API key found, Helicone integration enabled")
    logger.info(f"Gemini model: {settings.GEMINI_MODEL_NAME}")
    logger.info(f"OpenAI model: {settings.MODEL_NAME}")

# Configure the model list for the router
model_list = [
    {
        "model_name": "openai_model",  # Alias for the primary model
        "litellm_params": {
            "model": settings.MODEL_NAME,
            "api_key": settings.OPENAI_API_KEY,
        },
    },
    {
        "model_name": "gemini_model",  # Alias for the fallback model
        "litellm_params": {
            "model": settings.GEMINI_MODEL_NAME,
            "api_key": settings.GEMINI_API_KEY,
        },
    },
]

# Create a router instance
router = Router(model_list=model_list, fallbacks=[{"openai_model": ["gemini_model"]}])



class LLMServiceError(Exception):
    """Custom exception for AI service errors."""

    pass


class BaseLLMService:
    """
    Base class for AI services.

    Provides template methods for generating response from AI while allowing subclasses to override or extend any part as needed.
    """

    def __init__(self):
        self.model = "openai_model"  # Use the alias for the primary model
        
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

    async def _send_request(
        self,
        system_prompt,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        encoded_image: str = None,
        user_id: str = None,
        **kwargs
    ) -> str:
        """
        Send a request to the AI service using litellm.
        Args:
            system_prompt: The system prompt to set the context for the AI.
            prompt: The user input to generate a response for.
            max_tokens: Maximum number of tokens in the response.
            temperature: Sampling temperature for response variability.
            encoded_image: Optional base64 encoded image string.
            user_id: Optional user ID for tracking and rate limiting.
        Returns:
            The raw response content from the AI service.
        """
        if encoded_image:
            messages = [
                {"role": "system", "content": system_prompt},
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
                },
            ]
        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]


        if user_id:
            logger.info(f"Setting Helicone user ID for request tracking:{user_id}")
            litellm.metadata["Helicone-User-Id"] = user_id

        try:
            logger.info(f"Sending request to {self.model} via litellm router...")
            response = await router.acompletion(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
                metadata=litellm.metadata
            )
            logger.info(f"Successfully received response from {self.model} via litellm router")
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LiteLLM API error: {e}")
            raise LLMServiceError(f"LiteLLM API error: {e}")

    async def generate_response(
        self,
        system_prompt: str,
        request: Any,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        encoded_image: str = None,
        user_id: str = None,
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
            max_tokens=max_tokens,
            temperature=temperature,
            encoded_image=encoded_image,
            user_id=user_id,
        )
        if not should_parse:
            return raw
        return self._parse_response(raw)
