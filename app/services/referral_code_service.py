import logging
from datetime import datetime, timedelta
from supabase import create_client
from fastapi import HTTPException, status
from app.core.config import settings
from app.services.user_service import user_service

from app.utils.helper_functions import generate_random_string

logger = logging.getLogger(__name__)


class ReferralCodeService:
    def __init__(self):
        self.base_url = settings.SUPABASE_URL
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.client = create_client(self.base_url, self.api_key)

    async def save_referral_instance(self, user_id: str) -> str:
        try:
            user = await user_service.get_user_profile(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            name_prefix = user.first_name or generate_random_string(3)
            referral_code = f"{name_prefix.upper()}-{generate_random_string(5).upper()}"
            referral_data = {
                "referral_code": referral_code,
                "generated_by": user_id,
                "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
                "metadata": {},
                "created_at": datetime.now().isoformat(),
            }
            response = (
                self.client.table("referral_codes")
                .insert(referral_data)
                .execute()
                .model_dump()
            )
            referral_code_instance = response.get("data", [{}])[0]
            return referral_code_instance.get("referral_code")
        except Exception as e:
            logger.error(f"Error saving referral instance: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error saving referral code: {str(e)}",
            )


referral_code_service = ReferralCodeService()
