"""Contact form endpoints for the meal recommendation API.

This module contains FastAPI routes for handling contact form submissions
and customer support inquiries.
"""

import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Request
from typing import Optional
import httpx

from app.models.contact import ContactFormRequest, ContactFormResponse
from app.services.mail_service import mail_service
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


async def save_contact_submission(request: ContactFormRequest, reference_id: str, client_ip: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
    """Save contact form submission to database.
    
    Args:
        request: Contact form data
        reference_id: Generated reference ID
        client_ip: Client IP address (optional)
        user_agent: Client user agent (optional)
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        async with httpx.AsyncClient() as client:
            submission_data = {
                "reference_id": reference_id,
                "client_name": request.name,
                "client_email": request.email,
                "subject": request.subject,
                "message": request.message,
                "ip_address": client_ip,
                "user_agent": user_agent,
                "support_email_sent": False,  # Will be updated after email sends
                "confirmation_email_sent": False,  # Will be updated after email sends
            }
            
            if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
                logger.error("Supabase configuration missing for contact submission storage")
                return False
                
            response = await client.post(
                f"{settings.SUPABASE_URL}/rest/v1/contact_submissions",
                headers={
                    "apikey": str(settings.SUPABASE_SERVICE_ROLE_KEY),
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json=submission_data,
            )
            
            if response.status_code in (201, 200):
                logger.info(f"Contact submission saved to database: {reference_id}")
                return True
            else:
                logger.error(f"Failed to save contact submission to database: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Error saving contact submission to database: {str(e)}")
        return False


async def update_email_status(reference_id: str, support_sent: bool = False, confirmation_sent: bool = False) -> None:
    """Update email status in database.
    
    Args:
        reference_id: Reference ID of the submission
        support_sent: Whether support email was sent successfully
        confirmation_sent: Whether confirmation email was sent successfully
    """
    try:
        async with httpx.AsyncClient() as client:
            update_data = {}
            if support_sent:
                update_data["support_email_sent"] = True
            if confirmation_sent:
                update_data["confirmation_email_sent"] = True
                
            if update_data:
                if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
                    logger.error("Supabase configuration missing for email status update")
                    return
                    
                response = await client.patch(
                    f"{settings.SUPABASE_URL}/rest/v1/contact_submissions",
                    headers={
                        "apikey": str(settings.SUPABASE_SERVICE_ROLE_KEY),
                        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                        "Content-Type": "application/json",
                    },
                    params={"reference_id": f"eq.{reference_id}"},
                    json=update_data,
                )
                
                if response.status_code in (200, 204):
                    logger.info(f"Email status updated for {reference_id}: {update_data}")
                else:
                    logger.error(f"Failed to update email status: {response.status_code}")
                    
    except Exception as e:
        logger.error(f"Error updating email status: {str(e)}")


@router.post(
    "/submit",
    response_model=ContactFormResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit contact form",
    description="Submit a contact form message to MacroMeals support team. No authentication required.",
)
async def submit_contact_form(request: ContactFormRequest, http_request: Request) -> ContactFormResponse:
    """
    Submit a contact form message to the support team.
    
    This endpoint:
    - Accepts contact form submissions from clients
    - Saves submission to database for tracking
    - Sends notification email to support team
    - Sends confirmation email to the client
    - Generates a reference ID for tracking
    - Does not require authentication (public endpoint)
    
    Args:
        request: Contact form data including name, email, message, and optional subject
        http_request: FastAPI request object for extracting client metadata
        
    Returns:
        Confirmation response with success status and reference ID
        
    Raises:
        HTTPException: If there's an error processing the contact form
    """
    try:
        # Generate unique reference ID for tracking
        reference_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
        submission_time = datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")
        
        # Extract client information
        client_ip = http_request.client.host if http_request.client else None
        user_agent = http_request.headers.get("user-agent")
        
        logger.info(f"Processing contact form submission from {request.email} - Reference: {reference_id}")
        
        # Save to database first
        db_saved = await save_contact_submission(request, reference_id, client_ip, user_agent)
        if not db_saved:
            logger.warning(f"Failed to save contact submission to database, but continuing with email processing: {reference_id}")
        
        # Prepare subject line
        email_subject = request.subject if request.subject else "New Contact Form Inquiry"
        support_subject = f"[Contact Form] {email_subject}"
        
        # Track email sending status
        support_email_sent = False
        confirmation_email_sent = False
        
        # Send notification email to support team
        try:
            await mail_service.send_email(
                recipient=settings.EMAIL_SENDER,
                subject=support_subject,
                template_name="contact_form_notification.html",
                context={
                    "client_name": request.name,
                    "client_email": request.email,
                    "subject": request.subject,
                    "message": request.message,
                    "reference_id": reference_id,
                    "submission_time": submission_time,
                }
            )
            support_email_sent = True
            logger.info(f"Support notification sent for reference: {reference_id}")
        except Exception as e:
            logger.error(f"Failed to send support notification for {reference_id}: {str(e)}")
        
        # Send confirmation email to client
        try:
            await mail_service.send_email(
                recipient=request.email,
                subject="Thank you for contacting MacroMeals - Message Received",
                template_name="contact_form_confirmation.html",
                context={
                    "client_name": request.name,
                    "subject": request.subject,
                    "message": request.message,
                    "reference_id": reference_id,
                    "submission_time": submission_time,
                }
            )
            confirmation_email_sent = True
            logger.info(f"Confirmation email sent to {request.email} for reference: {reference_id}")
        except Exception as e:
            logger.error(f"Failed to send confirmation email for {reference_id}: {str(e)}")
        
        # Update email status in database
        if db_saved:
            await update_email_status(reference_id, support_email_sent, confirmation_email_sent)
        
        logger.info(f"Contact form submission processed successfully - Reference: {reference_id}")
        
        return ContactFormResponse(
            success=True,
            message="Thank you for your message! We've received your inquiry and will respond within 24 hours.",
            reference_id=reference_id
        )
        
    except Exception as e:
        logger.error(f"Unexpected error processing contact form: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="We're sorry, but there was an error processing your message. Please try again or email us directly at support@macromealsapp.com."
        ) 