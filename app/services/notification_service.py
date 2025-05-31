import os
import requests
import datetime
import logging
from typing import Optional

from supabase import create_client
from fastapi import HTTPException, status

import google.auth.transport.requests
from google.oauth2 import service_account

from app.core.config import settings
from app.models.notification import (
    Notification,
    NotificationResponse,
)

logger = logging.getLogger(__name__)


class FirebaseNotificationService:
    def __init__(self):
        self.SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]
        self.service_file = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ),
            "macro-meals-mobile-d3f2c02bc942.json",
        )

    def get_access_token(self) -> str:
        credentials = service_account.Credentials.from_service_account_file(
            self.service_file, scopes=self.SCOPES
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        return credentials.token

    def make_request(
        self, method: str, url: str, payload: Optional[dict] = None
    ) -> dict:
        try:
            response = requests.request(
                method=method,
                url=url,
                headers={
                    "Authorization": f"Bearer {self.get_access_token()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error making request: {str(e)}",
            )


class NotificationService:
    def __init__(self):
        self.base_url = settings.SUPABASE_URL
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.client = create_client(self.base_url, self.api_key)

    async def send_push_notification(
        self, fcm_token: str, title: str, body: str
    ) -> dict:
        return firebase_notification_service.make_request(
            method="POST",
            url="https://fcm.googleapis.com/v1/projects/macro-meals-mobile/messages:send",
            payload={
                "message": {
                    "token": fcm_token,
                    "notification": {
                        "title": title,
                        "body": body,
                    },
                    "data": {},
                }
            },
        )

    async def get_notifications(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        type: Optional[str] = None,
    ) -> Optional[NotificationResponse]:
        """
        Retrieve a paginated list of notifications for a specific user, with optional filtering by status and type.

        Args:
            user_id (str): The ID of the user whose notifications are to be retrieved.
            page (int, optional): The page number for pagination. Defaults to 1.
            page_size (int, optional): The number of notifications per page. Defaults to 20.
            status (Optional[str], optional): Filter notifications by status (e.g., 'read', 'unread'). Defaults to None.
            type (Optional[str], optional): Filter notifications by type. Defaults to None.

        Returns:
            Optional[NotificationResponse]: A response object containing the list of notifications, count, page, and page size.

        Raises:
            HTTPException: If an error occurs while retrieving notifications, an HTTP 500 error is raised.
        """
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
        """
        Asynchronously logs a notification to the 'notifications' table.
        Args:
            notification_data (dict): A dictionary containing the notification details to be logged.
        Returns:
            dict: A dictionary containing the logged notification data under the "data" key.
        Raises:
            HTTPException: If an unexpected error occurs while logging the notification,
                           an HTTP 500 error is raised with the error details.
        """
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
        """
        Mark a notification as read for a specific user.

        Args:
            notification_id (str): The ID of the notification to update.
            user_id (str): The ID of the user who owns the notification.
            status_ (str, optional): The new status to set (default is "read").

        Returns:
            dict: A message indicating the notification was marked as read.

        Raises:
            HTTPException: If the notification is not found or an error occurs during the update.
        """
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
firebase_notification_service = FirebaseNotificationService()
