
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from app.core.config import settings

import logging

# Setup logging for Slack alerts
logger = logging.getLogger(__name__)

def send_slack_alert(message, title=None):
    """Send alert to Slack with optional title."""
    try:
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        
        # Format message with title if provided
        formatted_message = f"*{title}*\n{message}" if title else message
        
        client.chat_postMessage(
            channel=settings.SLACK_ALERT_CHANNEL, 
            text=formatted_message,
            mrkdwn=True
        )
        logger.info(f"Slack alert sent: {message}")
    except SlackApiError as e:
        logger.error(f"Slack alert failed: {e.response['error']}")
    except Exception as e:
        logger.error(f"Error sending Slack alert: {str(e)}")