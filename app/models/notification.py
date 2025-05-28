from datetime import datetime
from re import sub
from typing import Annotated, Optional
from pydantic import BaseModel, Field, BeforeValidator

from app.utils.helper_functions import parse_datetime


class Notification(BaseModel):
    """
    Represents a notification sent to a user.

    Attributes:
        id (str): Unique identifier (matches Supabase notification ID).
        created_at (datetime): Timestamp when the notification was created.
        user_id (str): The ID of the user receiving the notification.
        type (Optional[str]): Type of notification (e.g., reminder, goal, system).
        subtype (Optional[str]): Further categorization (e.g., start_of_day, breakfast, macro_goal_completed).
        title (Optional[str]): Notification title text.
        body (Optional[str]): Main content/message of the notification.
        status (Optional[str]): Whether notification has been read or unread.
        delivered_at (datetime): Timestamp when the notification was delivered.
        read_at (datetime): Timestamp when the notification was read.
    """

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


class CreateNotificationRequest(BaseModel):
    """
    Request model for creating a new notification.

    Attributes:
        title (str): Notification title text.
        body (str): Main content/message of the notification.
        type (str): Type of notification (e.g., reminder, goal, system).
        subtype (Optional[str]): Further categorization (e.g., start_of_day, breakfast, macro_goal_completed).
    """

    title: str
    body: str
    type: str
    subtype: Optional[str] = None


class NotificationResponse(BaseModel):
    """
    Response model for a paginated list of notifications.

    Attributes:
        notifications (list[Notification]): List of notifications for the user.
        page (int): The current page number.
        page_size (int): The number of notifications to include on each page.
        count (int): The total number of notifications across all pages.
    """

    notifications: Annotated[
        list[Notification],
        Field(..., description="List of notifications for the user"),
    ]
    page: Annotated[int, Field(default=1, description="The current page number.")]
    page_size: Annotated[
        int,
        Field(
            default=20,
            description="The number of notifications to include on each page.",
        ),
    ]
    count: Annotated[
        int,
        Field(
            default=0,
            description="The total number of notifications across all pages.",
        ),
    ]


class LoggedNotification(Notification):
    """
    Represents a logged notification with creation timestamp.

    Inherits from Notification and overrides the created_at field to be required.
    """

    created_at: Annotated[
        datetime,
        Field(..., description="Date when the notification was created"),
        BeforeValidator(parse_datetime),
    ]


class UpdateNotificationStatusRequest(BaseModel):
    status: str
