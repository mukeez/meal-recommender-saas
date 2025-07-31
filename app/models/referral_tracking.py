from typing import Annotated
from unittest.mock import Base
from pydantic import BaseModel, Field, ConfigDict


class ReferralTracking(BaseModel):
    """Referral tracking model for managing referral codes and their usage."""

    id: Annotated[
        str, Field(..., description="Unique identifier for the referral code")
    ]
    referral_code: Annotated[
        str, Field(..., description="The actual referral code string")
    ]
    influencer_id: Annotated[
        str,
        Field(..., description="Identifier of the influencer who generated the code"),
    ]
    referred_user_id: Annotated[
        str, Field(..., description="Identifier of the user who used the referral code")
    ]
    date_used: Annotated[
        str, Field(..., description="Date when the referral code was used")
    ]
    created_at: Annotated[
        str, Field(..., description="Creation date and time of the referral code")
    ]
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
