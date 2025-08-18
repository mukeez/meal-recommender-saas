import asyncio
import logging
from datetime import datetime, date, time, timedelta, timezone
from supabase import create_client
from app.models.notification import NotificationSubtype
from app.services.meal_service import meal_service
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
            ).lt("trial_end_date", datetime.now().strftime("%Y-%m-%d"))
            logger.info("success")
        except Exception as e:
            logger.error(f"Failed to downgrade users with error: {e}")

    def has_received_notification_today(self, user_id: str, subtype: str) -> bool:
        """
        Check if a user has already received a notification of the given subtype today.

        Args:
            user_id (str): The user's ID
            subtype (str): The notification subtype (e.g., 'start_of_day', 'end_of_day', 'breakfast')

        Returns:
            bool: True if notification already sent today, False otherwise
        """
        today = date.today()
        start_of_day = datetime.combine(today, time.min, tzinfo=timezone.utc)
        end_of_day = datetime.combine(today, time.max, tzinfo=timezone.utc)

        existing_notification = (
            self.supabase_client.table("notifications")
            .select("id")
            .eq("user_id", user_id)
            .eq("type", "reminder")
            .eq("subtype", subtype)
            .gte("created_at", start_of_day.isoformat())
            .lte("created_at", end_of_day.isoformat())
            .execute()
        )

        return bool(existing_notification.data)

    def schedule_start_of_day_meal_reminders(self) -> None:
        """Schedule start of day meal reminders for users with meal_reminder_preferences_set as False."""
        try:
            logger.info("preparing to schedule start of day meal reminders")
            response = (
                self.supabase_client.table("user_profiles")
                .select("id, fcm_token, first_name")
                .eq("meal_reminder_preferences_set", False)
                .execute()
            )

            successful_notifications = 0
            failed_notifications = 0

            for user in response.data:
                user_id = user.get("id")
                token = user.get("fcm_token")
                first_name = user.get("first_name", None)

                if not token:
                    logger.warning(
                        f"No FCM token for user {user_id}, skipping notification"
                    )
                    continue

                if self.has_received_notification_today(
                    user_id, NotificationSubtype.START_OF_DAY.value
                ):
                    logger.info(
                        f"User {user_id} has already received start of day notification today, skipping"
                    )
                    continue

                try:
                    logger.info(
                        f"Sending meal reminder notification to user: {user_id}"
                    )
                    title = (
                        f"Good morning, {first_name}!"
                        if first_name
                        else "Good morning!"
                    )
                    body = "Ready to fuel your day right? Tap to plan your meals and hit those macro goals today!"

                    # Send push notification
                    asyncio.run(
                        notification_service.send_push_notification(
                            fcm_token=token,
                            title=title,
                            body=body,
                        )
                    )

                    # Log notification to database
                    self.supabase_client.table("notifications").insert(
                        {
                            "user_id": user_id,
                            "type": "reminder",
                            "subtype": NotificationSubtype.START_OF_DAY.value,
                            "title": title,
                            "body": body,
                            "status": "unread",
                        }
                    ).execute()

                    successful_notifications += 1
                    logger.info(
                        f"Successfully sent start of day reminder to user: {user_id} - {settings.ENVIRONMENT}"
                    )

                except Exception as user_error:
                    failed_notifications += 1
                    logger.error(
                        f"Failed to send start of day reminder to user {user_id}: {str(user_error)}"
                    )
                    continue  # Continue to next user

            logger.info(
                f"Start of day reminders completed: {successful_notifications} successful, {failed_notifications} failed"
            )

        except Exception as e:
            logger.error(
                f"Failed to schedule start of day meal reminders with error: {e}"
            )

    def schedule_end_of_day_meal_reminders(self) -> None:
        """Schedule end of day meal reminders for users with meal_reminder_preferences_set key as False."""
        try:
            logger.info("preparing to schedule end of day meal reminders")
            response = (
                self.supabase_client.table("user_profiles")
                .select("id, fcm_token, first_name")
                .eq("meal_reminder_preferences_set", False)
                .execute()
            )

            successful_notifications = 0
            failed_notifications = 0

            for user in response.data:
                user_id = user.get("id")
                token = user.get("fcm_token")
                first_name = user.get("first_name", None)

                if not token:
                    logger.warning(
                        f"No FCM token for user {user_id}, skipping notification"
                    )
                    continue

                if self.has_received_notification_today(
                    user_id, NotificationSubtype.END_OF_DAY.value
                ):
                    logger.info(
                        f"User {user_id} has already received end of day notification today, skipping"
                    )
                    continue

                try:
                    logger.info(
                        f"Sending end of day meal reminder notification to user: {user_id}"
                    )
                    title = (
                        f"Day is almost over, {first_name}!"
                        if first_name
                        else "Day is almost over!"
                    )
                    body = "Don't forget to log your meals. It only takes a minute to stay on track."

                    # Send push notification
                    asyncio.run(
                        notification_service.send_push_notification(
                            fcm_token=token,
                            title=title,
                            body=body,
                        )
                    )

                    # Log notification to database
                    self.supabase_client.table("notifications").insert(
                        {
                            "user_id": user_id,
                            "type": "reminder",
                            "subtype": NotificationSubtype.END_OF_DAY.value,
                            "title": title,
                            "body": body,
                            "status": "unread",
                        }
                    ).execute()

                    successful_notifications += 1
                    logger.info(
                        f"Successfully sent end of day reminder to user: {user_id} - {settings.ENVIRONMENT}"
                    )

                except Exception as user_error:
                    failed_notifications += 1
                    logger.error(
                        f"Failed to send end of day reminder to user {user_id}: {str(user_error)}"
                    )
                    continue  # Continue to next user

            logger.info(
                f"End of day reminders completed: {successful_notifications} successful, {failed_notifications} failed"
            )

        except Exception as e:
            logger.error(
                f"Failed to schedule end of day meal reminders with error: {e}"
            )

    def schedule_custom_meal_reminders_breakfast(self) -> None:
        """Schedule custom meal reminders for breakfast."""
        try:
            logger.info("scheduling custom meal reminders for breakfast")
            response = (
                self.supabase_client.table("user_profiles")
                .select("id, fcm_token, first_name")
                .eq("meal_reminder_preferences_set", True)
                .execute()
            )

            successful_notifications = 0
            failed_notifications = 0

            for user in response.data:
                user_id = user.get("id")
                token = user.get("fcm_token")
                first_name = user.get("first_name", None)

                if not token:
                    logger.warning(
                        f"No FCM token for user {user_id}, skipping notification"
                    )
                    continue

                if self.has_received_notification_today(
                    user_id, NotificationSubtype.BREAKFAST.value
                ):
                    logger.info(
                        f"User {user_id} has already received breakfast notification today, skipping"
                    )
                    continue

                try:
                    title = (
                        f"Time for breakfast, {first_name}!"
                        if first_name
                        else "Time for breakfast!"
                    )
                    body = "Log your morning meal to start your macro tracking off right today. 🍳"

                    # Send push notification
                    asyncio.run(
                        notification_service.send_push_notification(
                            fcm_token=token,
                            title=title,
                            body=body,
                        )
                    )

                    # Log notification to database
                    self.supabase_client.table("notifications").insert(
                        {
                            "user_id": user_id,
                            "type": "reminder",
                            "subtype": NotificationSubtype.BREAKFAST.value,
                            "title": title,
                            "body": body,
                            "status": "unread",
                        }
                    ).execute()

                    successful_notifications += 1
                    logger.info(
                        f"Successfully sent breakfast reminder to user: {user_id} - {settings.ENVIRONMENT}"
                    )

                except Exception as user_error:
                    failed_notifications += 1
                    logger.error(
                        f"Failed to send breakfast reminder to user {user_id}: {str(user_error)}"
                    )
                    continue  # Continue to next user

            logger.info(
                f"Breakfast reminders completed: {successful_notifications} successful, {failed_notifications} failed"
            )

        except Exception as e:
            logger.error(f"Failed to schedule breakfast reminders with error: {e}")

    def schedule_custom_meal_reminders_lunch(self) -> None:
        """Schedule custom meal reminders for lunch."""
        try:
            logger.info("scheduling custom meal reminders for lunch")
            response = (
                self.supabase_client.table("user_profiles")
                .select("id, fcm_token, first_name")
                .eq("meal_reminder_preferences_set", True)
                .execute()
            )

            successful_notifications = 0
            failed_notifications = 0

            for user in response.data:
                user_id = user.get("id")
                token = user.get("fcm_token")
                first_name = user.get("first_name", None)

                if not token:
                    logger.warning(
                        f"No FCM token for user {user_id}, skipping notification"
                    )
                    continue

                if self.has_received_notification_today(
                    user_id, NotificationSubtype.LUNCH.value
                ):
                    logger.info(
                        f"User {user_id} has already received lunch notification today, skipping"
                    )
                    continue

                try:
                    title = f"Lunchtime, {first_name}!" if first_name else "Lunchtime!"
                    body = "Take a moment to log your meal and see how your macros are stacking up. 🥗"

                    # Send push notification
                    asyncio.run(
                        notification_service.send_push_notification(
                            fcm_token=token,
                            title=title,
                            body=body,
                        )
                    )

                    # Log notification to database
                    self.supabase_client.table("notifications").insert(
                        {
                            "user_id": user_id,
                            "type": "reminder",
                            "subtype": NotificationSubtype.LUNCH.value,
                            "title": title,
                            "body": body,
                            "status": "unread",
                        }
                    ).execute()

                    successful_notifications += 1
                    logger.info(
                        f"Successfully sent lunch reminder to user: {user_id} - {settings.ENVIRONMENT}"
                    )

                except Exception as user_error:
                    failed_notifications += 1
                    logger.error(
                        f"Failed to send lunch reminder to user {user_id}: {str(user_error)}"
                    )
                    continue  # Continue to next user

            logger.info(
                f"Lunch reminders completed: {successful_notifications} successful, {failed_notifications} failed"
            )

        except Exception as e:
            logger.error(f"Failed to schedule lunch reminders with error: {e}")

    def schedule_custom_meal_reminders_dinner(self) -> None:
        """Schedule custom meal reminders for dinner."""
        try:
            logger.info("scheduling custom meal reminders for dinner")
            response = (
                self.supabase_client.table("user_profiles")
                .select("id, fcm_token, first_name")
                .eq("meal_reminder_preferences_set", True)
                .execute()
            )

            successful_notifications = 0
            failed_notifications = 0

            for user in response.data:
                user_id = user.get("id")
                token = user.get("fcm_token")
                first_name = user.get("first_name", None)

                if not token:
                    logger.warning(
                        f"No FCM token for user {user_id}, skipping notification"
                    )
                    continue

                if self.has_received_notification_today(
                    user_id, NotificationSubtype.DINNER.value
                ):
                    logger.info(
                        f"User {user_id} has already received dinner notification today, skipping"
                    )
                    continue

                try:
                    title = (
                        f"Dinner time, {first_name}!" if first_name else "Dinner time!"
                    )
                    body = "Log your evening meal to complete your day's macro tracking. What's on the menu? 🍽️"

                    # Send push notification
                    asyncio.run(
                        notification_service.send_push_notification(
                            fcm_token=token,
                            title=title,
                            body=body,
                        )
                    )

                    # Log notification to database
                    self.supabase_client.table("notifications").insert(
                        {
                            "user_id": user_id,
                            "type": "reminder",
                            "subtype": NotificationSubtype.DINNER.value,
                            "title": title,
                            "body": body,
                            "status": "unread",
                        }
                    ).execute()

                    successful_notifications += 1
                    logger.info(
                        f"Successfully sent dinner reminder to user: {user_id} - {settings.ENVIRONMENT}"
                    )

                except Exception as user_error:
                    failed_notifications += 1
                    logger.error(
                        f"Failed to send dinner reminder to user {user_id}: {str(user_error)}"
                    )
                    continue  # Continue to next user

            logger.info(
                f"Dinner reminders completed: {successful_notifications} successful, {failed_notifications} failed"
            )

        except Exception as e:
            logger.error(f"Failed to schedule dinner reminders with error: {e}")

    def send_trial_expiry_notification_24_hours_prior(self) -> None:
        """Send trial expiry notification 24 hours before the trial ends."""
        try:
            logger.info("preparing to send trial expiry notifications")
            response = (
                self.supabase_client.table("user_profiles")
                .select("id, fcm_token, first_name, trial_end_date")
                .eq("is_pro", False)
                .execute()
            )
            for user in response.data:
                user_id = user.get("id")
                token = user.get("fcm_token")
                first_name = user.get("first_name", None)
                trial_end_date = user.get("trial_end_date")
                if not trial_end_date:
                    continue

                trial_end_date = datetime.fromisoformat(trial_end_date).date()
                if trial_end_date - date.today() == timedelta(days=1):
                    if self.has_received_notification_today(
                        user_id, NotificationSubtype.TRIAL_EXPIRY.value
                    ):
                        logger.info(
                            f"User {user_id} has already received trial expiry notification today, skipping"
                        )
                        continue

                    if token:
                        title = (
                            f"{first_name}, your Macro Meals trial ends in 24 hours!"
                            if first_name
                            else "Your Macro Meals trial ends in 24 hours!"
                        )
                        body = "Don’t lose your tracking streak — upgrade now."
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
                                "subtype": NotificationSubtype.TRIAL_EXPIRY.value,
                                "title": title,
                                "body": body,
                                "status": "unread",
                            }
                        ).execute()
                        logger.info(
                            f"sent trial expiry notification to user: {user_id}"
                        )
        except Exception as e:
            logger.error(f"Failed to send trial expiry notifications: {e}")


macromeals_tasks = MacroMealsTasks()
