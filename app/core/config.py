"""Configuration settings for the meal recommendation API.

This module manages environment variables and application settings.
"""
import os
from dotenv import load_dotenv

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
        self.SUPABASE_BUCKET_NAME = os.getenv("SUPABASE_BUCKET_NAME", "avatars")


        # AI API Settings
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY environment variable is not set")

        self.MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4")


        # Nutritionix API Settings
        self.NUTRITIONIX_APP_ID = os.getenv("NUTRITIONIX_APP_ID")
        self.NUTRITIONIX_API_KEY = os.getenv("NUTRITIONIX_API_KEY")

        # Stripe API Settings
        self.STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
        self.STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
        self.STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
        self.STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

        # AWS SETTINGS
        self.AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
        self.AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.AWS_REGION = os.getenv("AWS_REGION")

        # Firebase Settings
        self.FIREBASE_SERVICE_ACCOUNT_FILE = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE")
        if not self.FIREBASE_SERVICE_ACCOUNT_FILE:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT_FILE environment variable is not set")
        self.FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
        if not self.FIREBASE_PROJECT_ID:
            raise ValueError("FIREBASE_PROJECT_ID environment variable is not set")        # Slack Settings
        self.SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
        self.SLACK_ALERT_CHANNEL = "#macromeals-alerts"

        # Redis Settings
        self.REDIS_HOST = os.getenv("REDIS_HOST", "redis")
        self.REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

        # Email Settings
        self.EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "support@macromealsapp.com")
        self.EMAIL_SENDER_NAME = os.environ.get("EMAIL_SENDER_NAME", "MacroMeals")




settings = Settings()