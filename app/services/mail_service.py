"""
MailService Module

This module provides email sending capabilities with template rendering using Jinja2.
"""

import boto3
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from app.core.config import settings
from typing import Dict, Any, List, Optional
import datetime

import logging

logger = logging.getLogger(__name__)

# Set up Jinja2 environment with proper auto-escaping and template inheritance
template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml']),
    enable_async=True  # Enable async rendering if needed
)


class MailService:
    """Mail service with template rendering capabilities."""

    def __init__(self):
        self.ses_client = boto3.client(
            "ses",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

    async def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Asynchronously render a Jinja template with the given context.
        
        Args:
            template_name: The name of the template file to render
            context: Dictionary of variables to pass to the template
            
        Returns:
            The rendered template as a string
        """
        try:
            template = jinja_env.get_template(template_name)
            # Use async rendering if the template environment is configured for it
            if jinja_env.is_async:
                return await template.render_async(**context)
            else:
                return template.render(**context)
        except Exception as e:
            logger.error(f"Error rendering template {template_name}: {str(e)}")
            raise ValueError(f"Error rendering template: {str(e)}")

    async def send_email(
        self,
        recipient: str,
        subject: str,
        template_name: str,
        context: Dict[str, Any],
        attachments: List[str] = None
    ) -> Dict[str, Any]:
        """
        Send an email using a Jinja template.
        
        Args:
            recipient: Email address of the recipient
            subject: Email subject line
            template_name: Name of the HTML template to use
            context: Dictionary of variables to pass to the template
            attachments: Optional list of file paths to attach
            
        Returns:
            Dictionary containing the status and response from SES
        """
        try:
            # Add current year to all templates
            context_with_year = {**context, "current_year": datetime.datetime.now().year}
            
            # Render the HTML template with all context variables
            html_content = await self.render_template(template_name, context_with_year)
            
            # Send the email
            response = self.send_mail(
                sender=settings.EMAIL_SENDER,
                sender_name=settings.EMAIL_SENDER_NAME,
                recipients=[recipient],
                title=subject,
                body=html_content,  # Pass the rendered HTML
                attachments=attachments
            )
            
            logger.info(f"Email sent successfully to {recipient}")
            return response
            
        except Exception as e:
            logger.error(f"Error sending email to {recipient}: {str(e)}")
            return {
                "status": False,
                "message": f"Failed to send email: {str(e)}",
                "message_id": "undefined"
            }

    def create_email_multipart_message(
        self,
        sender: str,
        sender_name: str,
        recipients: list,
        title: str,
        text: str = None,
        body: str = None,
        attachments: list = None,
    ) -> MIMEMultipart:
        """
        Creates a MIME multipart email message with optional plain text, HTML content, and attachments.

        The method constructs a MIME message of type `multipart/alternative` if both `text` and `body`
        are provided (for clients that support plain text or HTML), otherwise it defaults to `multipart/mixed`.

        Args:
            sender (str): The sender's email address.
            sender_name (str): Display name of the sender.
            recipients (list): List of primary recipient email addresses.
            title (str): Subject of the email.
            text (str, optional): Plain text version of the email body.
            body (str, optional): HTML version of the email body.
            attachments (list, optional): List of file paths to include as attachments.

        Returns:
            MIMEMultipart: The constructed email message ready to be sent.
        """
        if text and body:
            # assign subtype - multipart/alternative
            content_subtype = "alternative"
        else:
            # assign subtype - multipart/mixed
            content_subtype = "mixed"

        message = MIMEMultipart(content_subtype)
        message["Subject"] = title

        # if sender_name is provided, the format will be 'Sender Name <email@example.com>'
        if sender_name is None:
            message["From"] = f"{sender}"
        else:
            message["From"] = f"{sender_name} <{sender}>"

        message["To"] = ", ".join(recipients)

        # Record the MIME types of both parts:
        if text:
            part = MIMEText(text, "plain")
            message.attach(part)

        if body:
            part = MIMEText(body, "html")
            message.attach(part)

        # Add attachments
        for attachment in attachments or []:
            with open(attachment, "rb") as f:
                part = MIMEApplication(f.read())
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=os.path.basename(attachment),
                )
                message.attach(part)

        logger.info("Multipart message creation done!")
        return message

    def send_mail(
        self,
        sender: str,
        sender_name: str,
        recipients: list,
        title: str,
        text: str = None,
        body: str = None,
        attachments: list = None,
    ) -> dict:
        """
        Sends an email using AWS SES with optional plain text, HTML content, and attachments.

        Constructs a multipart email using `create_email_multipart_message()` and sends it via Amazon SES.

        Args:
            sender (str): The sender's email address.
            sender_name (str): Display name of the sender.
            recipients (list): List of recipient email addresses.
            title (str): Subject line of the email.
            text (str, optional): Plain text version of the email body.
            body (str, optional): HTML version of the email body.
            attachments (list, optional): List of file paths to be attached to the email.

        Returns:
            dict: A dictionary containing the status, message, SES message ID, and raw SES response.
                  If an error occurs, the message ID will be "undefined".
        """

        try:
            logger.info("Creating multipart message...")
            msg = self.create_email_multipart_message(
                sender, sender_name, recipients, title, text, body, attachments
            )

            logger.info("Sending Email to SES")

            destinations = []
            destinations.extend(recipients)
            ses_response = self.ses_client.send_raw_email(
                Source=sender,
                Destinations=destinations,
                RawMessage={"Data": msg.as_string()},
            )

        except ClientError as e:
            response = {
                "status": False,
                "message": e.response["Error"]["Message"],
                "message_id": "undefined",
                "response": e.response,
            }
            logger.error(f"Failed to send mail with error: {str(e)}")
            return response
        else:
            response = {
                "status": True,
                "message": "Email Successfully Sent.",
                "message_id": ses_response["MessageId"],
                "response": ses_response,
            }

            return response


mail_service = MailService()
