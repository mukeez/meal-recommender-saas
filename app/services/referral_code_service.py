import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from supabase import create_client
from fastapi import HTTPException, status
from app.core.config import settings
from app.services.user_service import user_service

from app.utils.helper_functions import generate_random_string, parse_datetime

logger = logging.getLogger(__name__)


class ReferralCodeService:
    def __init__(self):
        self.base_url = settings.SUPABASE_URL
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.client = create_client(self.base_url, self.api_key)

    def _parse_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        parsed = parse_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

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
                "access_type": "standard",
                "access_duration_days": 30,
                "is_active": True,
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

    def validate_referral_code(self, referral_code: str) -> Dict[str, Any]:
        try:
            response = (
                self.client.table("referral_codes")
                .select("*")
                .eq("referral_code", referral_code)
                .limit(1)
                .execute()
            )
            record = (response.data or [None])[0]
            if not record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Referral code not found",
                )

            if record.get("assigned_to_user_id"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Referral code has already been redeemed",
                )

            if record.get("is_active") is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Referral code is inactive",
                )

            expires_at = self._parse_datetime(record.get("expires_at"))
            if expires_at and expires_at < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Referral code has expired",
                )

            return record
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validating referral code {referral_code}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error validating referral code: {str(e)}",
            )

    def redeem_referral_code(self, user_id: str, referral_code: str) -> Dict[str, Any]:
        try:
            record = self.validate_referral_code(referral_code)
            access_type = record.get("access_type") or "standard"

            activation_date = datetime.now(timezone.utc)
            access_duration_days = record.get("access_duration_days") or 30
            expires_at = activation_date + timedelta(days=access_duration_days)

            update_payload: Dict[str, Any] = {
                "assigned_to_user_id": user_id,
                "activation_date": activation_date.isoformat(),
                "expires_at": expires_at.isoformat(),
                "is_active": access_type == "premium_free",
            }

            update_response = (
                self.client.table("referral_codes")
                .update(update_payload)
                .eq("id", record["id"])
                .is_("assigned_to_user_id", None)
                .eq("is_active", True)
                .execute()
            )

            updated_record = (update_response.data or [None])[0]
            if not updated_record:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Referral code is no longer available",
                )

            if access_type == "premium_free":
                self.client.table("user_profiles").update(
                    {"is_pro": True}
                ).eq("id", user_id).execute()

            logger.info(
                "Referral code redeemed",
                extra={
                    "referral_code": referral_code,
                    "user_id": user_id,
                    "access_type": access_type,
                    "access_duration_days": access_duration_days,
                    "expires_at": expires_at.isoformat(),
                },
            )

            return {
                "referral_code": referral_code,
                "access_type": access_type,
                "activation_date": activation_date.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error redeeming referral code {referral_code}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error redeeming referral code: {str(e)}",
            )

    def expire_premium_free_access(self) -> Tuple[int, int]:
        now = datetime.now(timezone.utc)
        expired_response = (
            self.client.table("referral_codes")
            .select("id, referral_code, assigned_to_user_id, expires_at")
            .eq("access_type", "premium_free")
            .eq("is_active", True)
            .lt("expires_at", now.isoformat())
            .execute()
        )
        expired_records = expired_response.data or []

        expired_count = 0
        downgraded_count = 0

        for record in expired_records:
            referral_id = record.get("id")
            user_id = record.get("assigned_to_user_id")
            referral_code = record.get("referral_code")

            self.client.table("referral_codes").update(
                {"is_active": False}
            ).eq("id", referral_id).execute()
            expired_count += 1

            logger.info(
                "Referral access expired",
                extra={
                    "referral_code": referral_code,
                    "user_id": user_id,
                    "expires_at": record.get("expires_at"),
                },
            )

            if not user_id:
                continue

            self.client.table("user_profiles").update(
                {"is_pro": False}
            ).eq("id", user_id).execute()
            downgraded_count += 1

            logger.info(
                "Referral access downgrade applied",
                extra={
                    "referral_code": referral_code,
                    "user_id": user_id,
                    "reason": "referral_access_expired",
                },
            )

        return expired_count, downgraded_count


referral_code_service = ReferralCodeService()
