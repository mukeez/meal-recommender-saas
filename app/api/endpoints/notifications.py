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
