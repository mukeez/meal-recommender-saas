from datetime import datetime
from typing import Annotated, Optional
from pydantic import BaseModel, Field, BeforeValidator

from app.utils.helper_functions import parse_datetime


class Notification(BaseModel):
    id: Annotated[
        str,
        Field(..., description="Unique identifier (matches Supabase notification ID)"),
    ]
    created_at: Annotated[
        datetime,
        Field(False, description="Timestamp when the notification was created"),
        BeforeValidator(parse_datetime),
    ]
    user_id: str
    type: Annotated[
        Optional[str],
        Field(None, description="Type of notification (e.g., reminder, goal, system)"),
    ]
    subtype: Annotated[
        Optional[str],
        Field(
            None,
            description="Further categorization (e.g., start_of_day, breakfast, macro_goal_completed)",
        ),
    ]
    title: Annotated[Optional[str], Field(None, description="Notification title text")]
    body: Annotated[Optional[str], Field(None, description="Main content/message")]
    status: Annotated[
        Optional[str],
        Field(None, description="Whether notification has been read or unread"),
    ]
    delivered_at: Annotated[
        datetime,
        Field(False, description="Timestamp when the notification was delivered"),
        BeforeValidator(parse_datetime),
    ]
    read_at: Annotated[
        datetime,
        Field(False, description="Timestamp when the notification was read"),
        BeforeValidator(parse_datetime),
    ]
