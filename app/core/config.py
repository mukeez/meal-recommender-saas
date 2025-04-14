"""Configuration settings for the meal recommendation API.

This module manages environment variables and application settings.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings.

    Attributes:
        API_V1_STR: API version path prefix
        PROJECT_NAME: Name of the project
        DEBUG: Debug mode flag
        OPENAI_API_KEY: API key for OpenAI API
        MODEL_NAME: AI model name to use for meal suggestions
    """
    def __init__(self):
        self.API_V1_STR = "/api/v1"
        self.PROJECT_NAME = "Meal Recommender API"
        self.DEBUG = os.getenv("DEBUG", "False").lower() == "true"

        # Supabase Settings
        self.SUPABASE_URL = os.getenv("SUPABASE_URL")
        self.SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


        # AI API Settings
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self.MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")


        # Nutritionix API Settings
        self.NUTRITIONIX_APP_ID = os.getenv("NUTRITIONIX_APP_ID")
        self.NUTRITIONIX_API_KEY = os.getenv("NUTRITIONIX_API_KEY")




settings = Settings()