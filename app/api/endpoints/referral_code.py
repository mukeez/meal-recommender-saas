import logging
from fastapi import APIRouter, Depends, HTTPException
from app.api.auth_guard import auth_guard
from app.services.referral_code_service import referral_code_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/generate",
    status_code=201,
    summary="Generate a new referral code",
    description="Generates a new referral code for the user.",
    response_model=dict,
)
async def generate_referral_code(
    user=Depends(auth_guard),
):
    """
    Generate a new referral code for the user.
    """
    try:
        referral_code = await referral_code_service.save_referral_instance(user["sub"])
        return {
            "data": referral_code,
            "message": "Referral code generated successfully.",
        }
    except Exception as e:
        logger.error(f"Error generating referral code for user {user['sub']}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while generating the referral code: {str(e)}",
        )
