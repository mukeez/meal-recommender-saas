import logging
from supabase import create_client
from fastapi import HTTPException, status
from app.core.config import settings
from app.models.referral_tracking import ReferralTrackingResponse


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

    async def get_influencer_tracking_stats(
        self, influencer_id: str
    ) -> ReferralTrackingResponse:
        """Get referral tracking stats for an influencer."""
        try:
            response = (
                self.client.table("referral_tracking")
                .select(
                    """
                    *,
                    user_profiles!referral_tracking_referred_user_id_fkey(
                        id,
                        first_name,
                        last_name,
                        email
                    )
                """
                )
                .eq("influencer_id", influencer_id)
                .execute()
                .model_dump()
            )

            tracking_data = response.get("data", [])

            if not tracking_data:
                return {
                    "total_users_referred": 0,
                    "referred_users": [],
                }

            referred_users = []
            for record in tracking_data:
                user_profile = record.get("user_profiles", {})
                referred_users.append(
                    {
                        "id": user_profile.get("id"),
                        "first_name": user_profile.get("first_name"),
                        "last_name": user_profile.get("last_name"),
                        "email": user_profile.get("email"),
                        "date_used": record.get("date_used"),
                    }
                )

            return ReferralTrackingResponse(
                total_users_referred=len(referred_users),
                referred_users=referred_users,
            )
        except Exception as e:
            logger.error(f"Error fetching referral tracking stats: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error fetching referral tracking stats: {str(e)}",
            )


referral_tracking_service = ReferralTrackingService()
