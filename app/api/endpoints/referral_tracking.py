import logging
from fastapi import APIRouter, HTTPException, Depends
from app.api.auth_guard import auth_guard
from app.models.referral_tracking import ReferralTrackingResponse
from app.services.referral_tracking_service import referral_tracking_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/influencer/{influencer_id}/stats",
    summary="Get referral tracking stats for an influencer",
    description="Fetches referral tracking statistics for a specific influencer.",
    response_model=ReferralTrackingResponse,
)
async def get_referral_tracking_stats(
    influencer_id: str,
    user=Depends(auth_guard),
) -> ReferralTrackingResponse:
    try:
        if user.get("sub") != influencer_id:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this influencer's stats.",
            )
        tracking_stats = await referral_tracking_service.get_influencer_tracking_stats(
            influencer_id
        )
        return tracking_stats
    except Exception as e:
        logger.error(
            f"Error fetching referral tracking stats for influencer {influencer_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while fetching referral tracking stats: {str(e)}",
        )
