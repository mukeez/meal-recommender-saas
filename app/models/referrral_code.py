from typing import Annotated
from unittest.mock import Base
from pydantic import BaseModel, Field, ConfigDict


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
    created_at: Annotated[
        str, Field(..., description="Creation date and time of the referral code")
    ]
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
