import logging
import random
import string
from datetime import datetime, date
from typing import Any
import json

from supabase import create_client
from app.core.config import settings

base_url = settings.SUPABASE_URL
api_key = settings.SUPABASE_SERVICE_ROLE_KEY
supabase_client = create_client(base_url, api_key)

logger = logging.getLogger(__name__)


def remove_null_values(d: dict) -> dict:
    return {key: value for key, value in d.items() if value is not None}


def parse_datetime(dt_str: Any) -> datetime | Any:
    """Parse a datetime string, handling timezone information.

    Args:
        dt_str: Datetime string to parse

    Returns:
        Parsed datetime object
    """
    if not dt_str:
        return datetime.now()

    if isinstance(dt_str, str):
        if "Z" in dt_str:
            dt_str = dt_str.replace("Z", "+00:00")

    try:
        return datetime.fromisoformat(dt_str)
    except:
        return datetime.now()


def deduplicate_dict_list(data):
    seen = set()
    deduplicated = []
    for d in data:
        key = json.dumps(d, sort_keys=True)
        if key not in seen:
            seen.add(key)
            deduplicated.append(d.copy())
    return deduplicated


def parse_date(value):
    """Parse date string to date object."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        # Parse ISO format date string (YYYY-MM-DD)
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid date format: {value}")


def generate_random_string(length: int = 5) -> str:
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


async def trigger_macro_goal_completion_notification(user_id: str) -> None:
    from datetime import datetime, date, time, timedelta, timezone

    from app.tasks.macromeals_tasks import MacroMealsTasks
    from app.services.meal_service import meal_service
    from app.services.notification_service import notification_service
    from app.models.notification import NotificationSubtype

    """Trigger a notification when a user logs their meal."""
    try:
        logger.info(f"Checking if user {user_id} has met their daily target...")

        today = date.today()
        start_of_day = datetime.combine(today, time.min, tzinfo=timezone.utc)
        end_of_day = datetime.combine(today, time.max, tzinfo=timezone.utc)

        existing_notification = (
            supabase_client.table("notifications")
            .select("id")
            .eq("user_id", user_id)
            .eq("type", "achievement")
            .eq("subtype", NotificationSubtype.MACRO_GOAL_COMPLETED.value)
            .gte("created_at", start_of_day.isoformat())
            .lte("created_at", end_of_day.isoformat())
            .execute()
        )

        has_received_notification_today = bool(existing_notification.data)

        if has_received_notification_today:
            logger.info(f"User {user_id} has already received notification today")
            return
        logger.info(f"User {user_id} has not received notification today")

        user_response = (
            supabase_client.table("user_profiles")
            .select("fcm_token, first_name")
            .eq("id", user_id)
            .single()
            .execute()
        )

        if not user_response.data:
            logger.warning(f"User {user_id} not found")
            return

        user_data = user_response.data
        token = user_data.get("fcm_token")
        first_name = user_data.get("first_name")

        if not token:
            logger.warning(f"No FCM token for user {user_id}, skipping notification")
            return

        try:
            daily_progress = await meal_service.get_daily_progress(user_id)
            progress_percentage = daily_progress.progress_percentage

            protein = progress_percentage.get("protein", 0)
            carbs = progress_percentage.get("carbs", 0)
            fat = progress_percentage.get("fat", 0)

        except Exception as e:
            logger.error(f"Error fetching daily progress for user {user_id}: {e}")
            return

        if not (protein >= 100 and carbs >= 100 and fat >= 100):
            logger.info(f"User {user_id} has not met all macro targets yet")
            return

        title = (
            f"You crushed it today, {first_name}!"
            if first_name
            else "You crushed it today!"
        )
        body = "You've hit all your macro targets perfectly. Keep up the amazing work!"

        await notification_service.send_push_notification(
            fcm_token=token,
            title=title,
            body=body,
        )

        supabase_client.table("notifications").insert(
            {
                "user_id": user_id,
                "type": "achievement",
                "subtype": NotificationSubtype.MACRO_GOAL_COMPLETED.value,
                "title": title,
                "body": body,
                "status": "unread",
            }
        ).execute()

        logger.info(f"sent macro goal completion notification to user: {user_id}")

    except Exception as e:
        logger.error(
            f"Failed to trigger macro goal completion notification for user {user_id}: {e}"
        )
