import logging
import traceback
from typing import Optional

from fastapi import APIRouter, Depends, status, HTTPException, Query
from app.api.auth_guard import auth_guard
from app.models.notification import (
    CreateNotificationRequest,
    NotificationResponse,
    UpdateNotificationStatusRequest,
)
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user notifications",
    description="Retrieve all notifications for the current user.",
)
async def get_user_notifications(
    user=Depends(auth_guard),
    page: int = Query(1, description="Current page number defaults to 1"),
    page_size: int = Query(
        20, description="Number of notifications to include on each page defaults to 20"
    ),
    status: Optional[str] = Query(None, description="Filter by notification status"),
    type: Optional[str] = Query(None, description="Filter by notification type"),
) -> NotificationResponse:
    """
    Retrieve a paginated list of notifications for the authenticated user.

    Args:
        user: The authenticated user object, injected by dependency.
        page (int, optional): The current page number for pagination. Defaults to 1.
        page_size (int, optional): The number of notifications per page. Defaults to 20.
        status (Optional[str], optional): Filter notifications by status (e.g., 'read', 'unread'). Defaults to None.
        type (Optional[str], optional): Filter notifications by type. Defaults to None.

    Returns:
        NotificationResponse: A paginated response containing the user's notifications.

    Raises:
        HTTPException: If an error occurs while retrieving notifications.
    """
    try:
        notifications = await notification_service.get_notifications(
            user_id=user["sub"],
            page=page,
            page_size=page_size,
            status=status,
            type=type,
        )
        return notifications
    except HTTPException:
        traceback.print_exc()
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Failed to retrieve user notifications"
        )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Log a user notification",
    description="Log a new notification for the current user.",
)
async def log_notification(
    notification: CreateNotificationRequest,
    user=Depends(auth_guard),
) -> dict:
    """
    Logs a notification for a user.

    Args:
        notification (CreateNotificationRequest): The notification data to be logged.
        user (dict, optional): The authenticated user information, injected via dependency.

    Returns:
        dict: A message indicating the result of the logging operation.

    Raises:
        HTTPException: If logging the notification fails or an HTTP-related error occurs.
    """
    try:
        notification_data = notification.model_dump()
        notification_data["user_id"] = user["sub"]
        await notification_service.log_notification(notification_data)
        return {"message": "Notification logged successfully"}
    except HTTPException:
        traceback.print_exc()
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to log notification")


@router.patch(
    "/{notification_id}/read",
    status_code=status.HTTP_200_OK,
    summary="Update notification status",
    description="Mark a notification as read.",
)
async def update_notification_status(
    notification_id: str,
    body: UpdateNotificationStatusRequest,
    user=Depends(auth_guard),
) -> dict:
    """
    Mark a notification as read for the current user.

    Args:
        notification_id (str): The ID of the notification to update.
        body (UpdateNotificationStatusRequest): The request body containing the new status.
        user: The authenticated user (injected by dependency).

    Returns:
        dict: A message indicating the notification status was updated.

    Raises:
        HTTPException: If the update fails or an error occurs.
    """
    try:
        await notification_service.mark_notification_as_read(
            user_id=user["sub"], notification_id=notification_id, status_=body.status
        )
        return {"message": "Notification status updated successfully"}
    except HTTPException:
        traceback.print_exc()
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Failed to update notification status"
        )
