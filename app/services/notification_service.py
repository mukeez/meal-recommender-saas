import datetime
import logging
from typing import Optional

from supabase import create_client
from fastapi import HTTPException, status
from app.core.config import settings
from app.models.notification import (
    Notification,
    NotificationResponse,
)

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self):
        self.base_url = settings.SUPABASE_URL
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.client = create_client(self.base_url, self.api_key)

    async def get_notifications(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        type: Optional[str] = None,
    ) -> Optional[NotificationResponse]:
        try:
            query = (
                self.client.table("notifications").select("*").eq("user_id", user_id)
            )
            if status:
                query = query.eq("status", status)
            if type:
                query = query.eq("type", type)
            response = (
                query.order("created_at", desc=True)
                .limit(page_size)
                .offset((page - 1) * page_size)
                .execute()
                .model_dump()
            )
            notifications = response["data"] or []
            logger.info(
                f"Retrieved {len(notifications)} notifications for user {user_id}"
            )
            notifications = [
                Notification(**notification) for notification in notifications
            ]
            return NotificationResponse(
                notifications=notifications,
                count=len(notifications),
                page=page,
                page_size=page_size,
            )
        except Exception as e:
            logger.error(f"Unexpected error retrieving notifications: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error retrieving user notifications: {str(e)}",
            )

    async def log_notification(self, notification_data: dict) -> dict:
        try:
            response = (
                self.client.table("notifications")
                .insert(notification_data)
                .execute()
                .model_dump()
            )
            logged_notification_data = response["data"]
            logger.info("Notification logged successfully")
            return {"data": logged_notification_data}
        except Exception as e:
            logger.error(f"Unexpected error logging notification: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error logging notification: {str(e)}",
            )

    async def mark_notification_as_read(
        self, notification_id: str, user_id: str, status_: str = "read"
    ) -> dict:
        try:
            response = (
                self.client.table("notifications")
                .update({"status": status_, "read_at": str(datetime.datetime.now())})
                .eq("id", notification_id)
                .eq("user_id", user_id)
                .execute()
                .model_dump()
            )
            if response["data"]:
                logger.info(f"Notification {notification_id} marked as read")
                return {"message": "Notification marked as read"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Notification not found",
                )
        except Exception as e:
            logger.error(f"Unexpected error marking notification as read: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error marking notification as read: {str(e)}",
            )


notification_service = NotificationService()
