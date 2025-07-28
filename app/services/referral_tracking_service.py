import logging
from supabase import create_client
from fastapi import HTTPException, status
from app.core.config import settings


logger = logging.getLogger(__name__)


class ReferralTrackingService:
    """Service for tracking referral codes and their usage."""

    def __init__(self):
        self.base_url = settings.SUPABASE_URL
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.client = create_client(self.base_url, self.api_key)

    async def log_referral_tracking(self, referral_tracking_data: dict) -> dict:
        """Log referral tracking data."""
        try:
            response = (
                self.client.table("referral_tracking")
                .insert(referral_tracking_data)
                .execute()
                .model_dump()
            )
            return {
                "message": "Referral tracking logged successfully",
                "data": response,
            }
        except Exception as e:
            logger.error(f"Error logging referral tracking: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error logging referral tracking: {str(e)}",
            )


referral_tracking_service = ReferralTrackingService()
