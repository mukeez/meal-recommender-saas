import asyncio
import logging
from datetime import datetime
from supabase import create_client
from app.core.config import settings
from app.services.notification_service import notification_service


logger = logging.getLogger(__name__)


class MacroMealsTasks:
    """Scheduled tasks to be executed at specific periods."""

    def __init__(self):
        self.base_url = settings.SUPABASE_URL
        self.api_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.supabase_client = create_client(self.base_url, self.api_key)

    def downgrade_users(self) -> None:
        """Downgrade users whose trial or subscription period has ended.

        Sets 'is_pro' to False for users who are currently pro and whose
        account was created before the current time."""
        try:
            logger.info("preparing to downgrade users with subscriptions ended")
            self.supabase_client.table("user_profiles").update({"is_pro": False}).eq(
                "is_pro", True
            ).lt("created_at", datetime.now().isoformat())
            logger.info("success")
        except Exception as e:
            logger.error(f"Failed to downgrade users with error: {e}")

    def schedule_start_of_day_meal_reminders(self) -> None:
        """Schedule start of day meal reminders for users with meal_reminder_preferences_set as False."""
        try:
            logger.info("preparing to schedule start of day meal reminders")
            users = (
                self.supabase_client.table("user_profiles")
                .select("id, fcm_token, first_name")
                .eq("meal_reminder_preferences_set", False)
                .execute()
            )
            user_list = users.data if hasattr(users, "data") else users
            for user in user_list:
                user_id = user.get("id")
                token = user.get("fcm_token")
                first_name = user.get("first_name", None)
                if token:
                    logger.info(
                        f"Sending meal reminder notification to user: {user_id}"
                    )
                    title = (
                        f"Good morning, {first_name}!"
                        if first_name
                        else "Good morning!"
                    )
                    body = "Ready to fuel your day right? Tap to plan your meals and hit those macro goals today!"
                    asyncio.run(
                        notification_service.send_push_notification(
                            fcm_token=token,
                            title=title,
                            body=body,
                        )
                    )
                    self.supabase_client.table("notifications").insert(
                        {
                            "user_id": user_id,
                            "type": "reminder",
                            "subtype": "start_of_day",
                            "title": title,
                            "body": body,
                            "status": "unread",
                        }
                    ).execute()
        except Exception as e:
            logger.error(
                f"Failed to schedule start of day meal reminders with error: {e}"
            )

    def schedule_end_of_day_meal_reminders(self) -> None:
        """Schedule end of day meal reminders for users with meal_reminder_preferences_set key as False."""
        try:
            logger.info("preparing to schedule end of day meal reminders")
            users = (
                self.supabase_client.table("user_profiles")
                .select("id, fcm_token, first_name")
                .eq("meal_reminder_preferences_set", False)
                .execute()
            )
            user_list = users.data if hasattr(users, "data") else users
            for user in user_list:
                user_id = user.get("id")
                token = user.get("fcm_token")
                first_name = user.get("first_name", None)
                if token:
                    logger.info(
                        f"Sending end of day meal reminder notification to user: {user_id}"
                    )
                    title = (
                        f"Day is almost over, {first_name}!"
                        if first_name
                        else "Day is almost over!"
                    )
                    body = "Don’t forget to log your meals. It only takes a minute to stay on track."
                    asyncio.run(
                        notification_service.send_push_notification(
                            fcm_token=token,
                            title=title,
                            body=body,
                        )
                    )
                    self.supabase_client.table("notifications").insert(
                        {
                            "user_id": user_id,
                            "type": "reminder",
                            "subtype": "end_of_day",
                            "title": title,
                            "body": body,
                            "status": "unread",
                        }
                    ).execute()
        except Exception as e:
            logger.error(
                f"Failed to schedule end of day meal reminders with error: {e}"
            )

    def schedule_custom_meal_reminders_breakfast(self) -> None:
        """Schedule custom meal reminders for breakfast."""
        try:
            logger.info("scheduling custom meal reminders for breakfast")
            users = (
                self.supabase_client.table("user_profiles")
                .select("id, fcm_token, first_name")
                .eq("meal_reminder_preferences_set", True)
                .execute()
            )
            user_list = users.data if hasattr(users, "data") else users
            for user in user_list:
                user_id = user.get("id")
                token = user.get("fcm_token")
                first_name = user.get("first_name", None)
                if token:
                    title = (
                        f"Time for breakfast, {first_name}!"
                        if first_name
                        else "Time for breakfast!"
                    )
                    body = "Log your morning meal to start your macro tracking off right today. 🍳"
                    asyncio.run(
                        notification_service.send_push_notification(
                            fcm_token=token,
                            title=title,
                            body=body,
                        )
                    )
                    self.supabase_client.table("notifications").insert(
                        {
                            "user_id": user_id,
                            "type": "reminder",
                            "subtype": "breakfast",
                            "title": title,
                            "body": body,
                            "status": "unread",
                        }
                    ).execute()
        except Exception as e:
            logger.error(f"Failed to schedule breakfast reminders with error: {e}")

    def schedule_custom_meal_reminders_lunch(self) -> None:
        """Schedule custom meal reminders for lunch."""
        try:
            logger.info("scheduling custom meal reminders for lunch")
            users = (
                self.supabase_client.table("user_profiles")
                .select("id, fcm_token, first_name")
                .eq("meal_reminder_preferences_set", True)
                .execute()
            )
            user_list = users.data if hasattr(users, "data") else users
            for user in user_list:
                user_id = user.get("id")
                token = user.get("fcm_token")
                first_name = user.get("first_name", None)
                if token:
                    title = f"Lunchtime, {first_name}!" if first_name else "Lunchtime!"
                    body = "Take a moment to log your meal and see how your macros are stacking up. 🥗"
                    asyncio.run(
                        notification_service.send_push_notification(
                            fcm_token=token,
                            title=title,
                            body=body,
                        )
                    )
                    self.supabase_client.table("notifications").insert(
                        {
                            "user_id": user_id,
                            "type": "reminder",
                            "subtype": "lunch",
                            "title": title,
                            "body": body,
                            "status": "unread",
                        }
                    ).execute()
        except Exception as e:
            logger.error(f"Failed to schedule lunch reminders with error: {e}")

    def schedule_custom_meal_reminders_dinner(self) -> None:
        """Schedule custom meal reminders for dinner."""
        try:
            logger.info("scheduling custom meal reminders for dinner")
            users = (
                self.supabase_client.table("user_profiles")
                .select("id, fcm_token, first_name")
                .eq("meal_reminder_preferences_set", True)
                .execute()
            )
            user_list = users.data if hasattr(users, "data") else users
            for user in user_list:
                user_id = user.get("id")
                token = user.get("fcm_token")
                first_name = user.get("first_name", None)
                if token:
                    title = (
                        f"Dinner time, {first_name}!" if first_name else "Dinner time!"
                    )
                    body = "Log your evening meal to complete your day's macro tracking. What's on the menu? 🍽️"
                    asyncio.run(
                        notification_service.send_push_notification(
                            fcm_token=token,
                            title=title,
                            body=body,
                        )
                    )
                    self.supabase_client.table("notifications").insert(
                        {
                            "user_id": user_id,
                            "type": "reminder",
                            "subtype": "dinner",
                            "title": title,
                            "body": body,
                            "status": "unread",
                        }
                    ).execute()
        except Exception as e:
            logger.error(f"Failed to schedule dinner reminders with error: {e}")


macromeals_tasks = MacroMealsTasks()
