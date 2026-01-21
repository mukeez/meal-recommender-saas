from typing import Annotated, Optional
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


class ReferralAccessType(str, Enum):
    STANDARD = "standard"
    PREMIUM_FREE = "premium_free"


class ReferralCode(BaseModel):
    """Referral code model for tracking referral codes in the system."""

    id: Annotated[
        str, Field(..., description="Unique identifier for the referral code")
    ]
    referral_code: Annotated[
        str, Field(..., description="The actual referral code string")
    ]
    generated_by: Annotated[
        str, Field(..., description="Identifier of the user who generated the code")
    ]
    expires_at: Annotated[
        str, Field(..., description="Expiration date and time of the referral code")
    ]
    metadata: Annotated[
        dict,
        Field(
            default_factory=dict,
            description="Additional metadata for the referral code",
        ),
    ]
    access_type: Annotated[
        ReferralAccessType,
        Field(ReferralAccessType.STANDARD, description="Access type granted by code"),
    ]
    access_duration_days: Annotated[
        int, Field(30, description="Number of days premium access lasts")
    ]
    activation_date: Annotated[
        Optional[str],
        Field(None, description="Timestamp when the referral code was redeemed"),
    ]
    assigned_to_user_id: Annotated[
        Optional[str],
        Field(None, description="User ID that redeemed the referral code"),
    ]
    is_active: Annotated[
        bool, Field(True, description="Whether the referral-based access is active")
    ]
    created_at: Annotated[
        str, Field(..., description="Creation date and time of the referral code")
    ]
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class RedeemReferralCodeRequest(BaseModel):
    referral_code: Annotated[
        str, Field(..., description="Referral code to redeem")
    ]
