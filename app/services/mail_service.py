"""
MailService Module

This module provides the `MailService` class which facilitates the creation and sending of multipart emails
(via plain text, HTML, and optional attachments) using Amazon SES (Simple Email Service).

Classes:
    - MailService: Handles MIME message generation and email transmission using AWS SES.
"""

import boto3
import os

from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from app.core.config import settings

import logging

logger = logging.getLogger(__name__)


class MailService:
    """
    Handles the creation and sending of multipart email messages through Amazon SES.

    This service supports plain text and HTML email bodies, multiple recipients, optional CC/BCC fields,
    and file attachments. Emails are constructed using MIME and transmitted via AWS SES.

    Attributes:
        ses_client (boto3.client): The initialized AWS SES client.
    """

    def __init__(self):
        self.ses_client = boto3.client(
            "ses",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )

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
