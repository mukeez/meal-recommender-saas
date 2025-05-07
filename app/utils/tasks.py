from supabase import create_client
from app.core.config import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MacroMealsTasks:
    """Scheduled tasks to be executed at specific periods."""
    def __init__(self):
        self.base_url = settings.SUPABASE_URL
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.supabase_client = create_client(self.base_url, self.api_key)

    def downgrade_users(self) -> None:
        """Downgrade users whose trial or subscription period has ended.

        Sets 'is_pro' to False for users who are currently pro and whose 
        account was created before the current time."""
        try:
            logger.info("preparing to downgrade users with subscriptions ended")
            self.supabase_client.table("user_profiles").update({"is_pro":False}).eq("is_pro", True).lt("created_at", datetime.now().isoformat())
            logger.info("success")
        except Exception as e:
            logger.error(f"Failed to downgrade users with error: {e}") 

macromeals_tasks = MacroMealsTasks()