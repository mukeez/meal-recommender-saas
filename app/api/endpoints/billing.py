import logging
from fastapi import APIRouter, Depends, Request, HTTPException, status, Header, Query
from datetime import datetime

from app.api.auth_guard import auth_guard
from app.models.billing import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    SubscriptionUpdate,
    SubscriptionStatus,
    SetupIntentResponse,
    BillingPortalResponse,
    PublishableKey,
)
from typing import Dict, Any, Optional
from app.services.stripe_service import stripe_service, StripeServiceError
from app.services.mail_service import mail_service
from app.services.user_service import user_service
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/stripe-config",
    status_code=status.HTTP_200_OK,
    response_model=PublishableKey,
    summary="Retrieve stripe publishable key",
    description="Retrieve stripe publishable key",
)
async def get_stripe_config(user=Depends(auth_guard)) -> PublishableKey:
    try:
        if not settings.STRIPE_PUBLISHABLE_KEY:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Publishable key does not exist",
            )
        return PublishableKey(publishable_key=settings.STRIPE_PUBLISHABLE_KEY)
    except HTTPException as e:
        raise
    except Exception as e:
        logger.info(
            f"An unexpected error occured while retrieving publishable key: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occured"
        )


@router.post(
    "/checkout",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Create Stripe checkout session",
    description="Create a Stripe checkout session for subscription with a 7-day free trial",
)
async def create_checkout_session(
    request: CheckoutSessionRequest, user=Depends(auth_guard)
) -> CheckoutSessionResponse:
    try:
        if request.user_id != user.get("sub"):
            logger.warning(f"User ID mismatch: {request.user_id} vs {user.get('sub')}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User ID in request does not match authenticated user",
            )

        checkout_session = await stripe_service.create_checkout_session(
            email=request.email, user_id=request.user_id, plan=request.plan
        )

        return checkout_session

    except HTTPException as e:
        raise
    except StripeServiceError as e:
        logger.error(f"Stripe service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating checkout session: {str(e)}",
        )

    except Exception as e:
        logger.error(f"Unexpected error creating checkout session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Process Stripe webhook events",
    description="Process Stripe webhook events for subscription management",
)
async def stripe_webhook(
    request: Request, stripe_signature: str = Header(..., alias="Stripe-Signature")
) -> dict:
    try:
        payload = await request.body()

        event = stripe_service.verify_webhook_signature(payload, stripe_signature)
        
        # Get event ID for idempotency protection
        event_id = event.get("id")
        if not event_id:
            logger.warning("Received webhook event without ID")
            return {"status": "success", "message": "Event received but no ID found"}
        
        # Check if we've already processed this event
        is_processed = await stripe_service.is_webhook_event_processed(event_id)
        if is_processed:
            logger.info(f"Event {event_id} already processed, skipping")
            return {"status": "success", "message": f"Event {event_id} already processed"}
        
        # Mark event as being processed
        await stripe_service.mark_webhook_event_processed(event_id)
        logger.info(f"Processing webhook event: {event['type']} (ID: {event_id})")

        if event["type"] == "setup_intent.succeeded":
            session = event["data"]["object"]
            payment_method = session["payment_method"]
            customer_id = session["customer"]
            plan = session["metadata"].get("plan")
            user_id = session["metadata"].get("user_id")
            
            # Check if user already has an active subscription before creating a new one
            if user_id:
                try:
                    has_active_sub = await stripe_service.has_active_subscription(user_id)
                    if has_active_sub:
                        logger.warning(f"User {user_id} already has an active subscription, skipping subscription creation")
                        return {
                            "status": "success", 
                            "message": "User already has an active subscription, setup intent processed but no new subscription created"
                        }
                except Exception as e:
                    logger.warning(f"Failed to check subscription status for user {user_id}: {str(e)}")
                    # Continue with subscription creation if check fails (fail open)
            
            # create subscription for user
            await stripe_service.create_subscription(
                customer_id=customer_id,
                payment_method_id=payment_method,
                user_id=user_id,
                plan=plan
            )
            
            # Mark trial as used if this is the user's first subscription
            if user_id:
                try:
                    await user_service.mark_trial_as_used(user_id)
                    logger.info(f"Trial marked as used for user: {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to mark trial as used for user {user_id}: {str(e)}")
            
            # Get customer email and send welcome email
            try:
                customer_email = await stripe_service.get_customer_email(customer_id)
                if customer_email:
                    # Check if user has trial to determine email content
                    has_trial = session["metadata"].get("has_trial", "true").lower() == "true"
                    trial_days = 7 if has_trial else 0
                    
                    await mail_service.send_email(
                        recipient=customer_email,
                        subject="Welcome to Macro Meals Pro!",
                        template_name="subscription_created.html",
                        context={
                            "subscription_type": "Macro Meals Pro",
                            "trial_days": trial_days,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to send welcome email for customer {customer_id}: {str(e)}")
            
            logger.info(f"Subscription created for user: {customer_id}")
            return {
                "status": "success",
                "message": "Setup intent and subscription creation completed successfully",
            }

        elif event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            user_id = await stripe_service.handle_checkout_completed(session)
            
            # Mark trial as used for checkout flow (if user has trial)
            metadata = session.get("metadata", {})
            has_trial = metadata.get("has_trial", "true").lower() == "true"
            if user_id and has_trial:
                try:
                    await user_service.mark_trial_as_used(user_id)
                    logger.info(f"Trial marked as used for user: {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to mark trial as used for user {user_id}: {str(e)}")
                    
            
            # Get customer email from session and send welcome email
            try:
                customer_email = session.get("customer_details", {}).get("email")
                if customer_email:
                    trial_days = 7 if has_trial else 0
                    await mail_service.send_email(
                        recipient=customer_email,
                        subject="Welcome to Macro Meals Pro!",
                        template_name="subscription_created.html",
                        context={
                            "subscription_type": "Macro Meals Pro",
                            "trial_days": trial_days,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to send welcome email for user {user_id}: {str(e)}")
                
            logger.info(f"Checkout completed for user: {user_id}")
            return {"status": "success", "message": "Checkout completed successfully"}
        
        elif event["type"] == "customer.subscription.created":
            
            session = event["data"]["object"]
            customer_id = session["customer"]
            session_trial_end_date = session["trial_end"]
            trial_end_date = datetime.fromtimestamp(session_trial_end_date).date()

            await stripe_service.update_stripe_user_subscription(
                customer=customer_id,
                subscription_data=SubscriptionUpdate(
                    is_pro=None,
                    stripe_subscription_id=None,
                    subscription_start=None,
                    subscription_end=None,
                    trial_end_date=trial_end_date.isoformat(),
                    plan=None
                ),
            )
            logger.info(
                f"Subscription created for user: {customer_id} with trial end date: {trial_end_date}"
            )
            return {
                "status": "success",
                "message": "Subscription created successfully",
            }

        elif event["type"] == "customer.subscription.deleted":
            session = event["data"]["object"]
            customer_id = session["customer"]
            await stripe_service.update_stripe_user_subscription(
                customer=customer_id,
                subscription_data=SubscriptionUpdate(
                    is_pro=False,
                    stripe_subscription_id=None,
                    subscription_start=None,
                    subscription_end=None,
                    trial_end_date=None,
                    plan=None
                ),
            )
            
            # send cancellation email
            try:
                customer_email = await stripe_service.get_customer_email(customer_id)
                if customer_email:
                    await mail_service.send_email(
                        recipient=customer_email,
                        subject="Your Macro Meals Pro Subscription",
                        template_name="subscription_cancelled.html",
                        context={
                            "subscription_type": "Macro Meals Pro",
                            "cancellation_date": datetime.now().strftime("%B %d, %Y")
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to send cancellation email for customer {customer_id}: {str(e)}")
                # Don't fail the webhook for email failures
            
            return {
                "status": "success",
                "message": "Subscription cancelled successfully",
            }

        # update subscription start and end dates
        elif event["type"] == "invoice.paid":
            session = event["data"]["object"]
            customer = session["customer"]
            subscription_start = datetime.fromtimestamp(
                session["lines"]["data"][0]["period"]["start"]
            ).isoformat()
            subscription_end = datetime.fromtimestamp(
                session["lines"]["data"][0]["period"]["end"]
            ).isoformat()
            subscription_data = SubscriptionUpdate(
                subscription_start=subscription_start,
                subscription_end=subscription_end,
                is_pro=True,
                stripe_subscription_id=None,
                trial_end_date=None,
                plan=None
            )
            await stripe_service.update_stripe_user_subscription(
                customer=customer, subscription_data=subscription_data
            )
            return {"status": "success", "message": "Subscription renewed"}

        elif event["type"] == "invoice.payment_failed":
            invoice = event["data"]["object"]
            customer_id = invoice["customer"]
            subscription_id = invoice["subscription"]
            
            logger.warning(f"Payment failed for customer {customer_id}, subscription {subscription_id}")
            
            try:
                customer_email = await stripe_service.get_customer_email(customer_id)
                if customer_email:
                    await mail_service.send_email(
                        recipient=customer_email,
                        subject="Payment Failed - MacroMeals Subscription",
                        template_name="payment_failed.html",
                        context={
                            "customer_email": customer_email,
                            "invoice_url": invoice.get("hosted_invoice_url"),
                            "amount_due": f"£{invoice['amount_due'] / 100:.2f}",
                            "next_payment_attempt": invoice.get("next_payment_attempt")
                        }
                    )
                    logger.info(f"Payment failure notification sent to {customer_email}")
            except Exception as e:
                logger.warning(f"Failed to send payment failure email for customer {customer_id}: {str(e)}")
            
            return {"status": "success", "message": "Payment failure processed"}

        elif event["type"] == "customer.subscription.updated":
            subscription = event["data"]["object"]
            customer_id = subscription["customer"]
            subscription_status = subscription["status"]
            
            logger.info(f"Subscription status updated for customer {customer_id}: {subscription_status}")
            
            if subscription_status == "past_due":
                logger.warning(f"Subscription past due for customer {customer_id}")
                
                try:
                    customer_email = await stripe_service.get_customer_email(customer_id)
                    if customer_email:
                        await mail_service.send_email(
                            recipient=customer_email,
                            subject="Subscription Past Due - MacroMeals",
                            template_name="subscription_past_due.html",
                            context={
                                "customer_email": customer_email,
                                "subscription_id": subscription["id"]
                            }
                        )
                        logger.info(f"Past due notification sent to {customer_email}")
                except Exception as e:
                    logger.warning(f"Failed to send past due email for customer {customer_id}: {str(e)}")
                
            elif subscription_status == "canceled":
                logger.info(f"Subscription canceled due to failed payments for customer {customer_id}")
                
                subscription_data = SubscriptionUpdate(
                    is_pro=False,
                    stripe_subscription_id=None,
                    subscription_start=None,
                    subscription_end=None,
                    trial_end_date=None,
                    plan=None
                )
                await stripe_service.update_stripe_user_subscription(
                    customer=customer_id, subscription_data=subscription_data
                )
                
                try:
                    customer_email = await stripe_service.get_customer_email(customer_id)
                    if customer_email:
                        await mail_service.send_email(
                            recipient=customer_email,
                            subject="Subscription Canceled - MacroMeals",
                            template_name="subscription_cancelled.html",
                            context={
                                "customer_email": customer_email,
                                "reason": "payment_failure"
                            }
                        )
                        logger.info(f"Cancellation notification sent to {customer_email}")
                except Exception as e:
                    logger.warning(f"Failed to send cancellation email for customer {customer_id}: {str(e)}")
                
            return {"status": "success", "message": f"Subscription status updated: {subscription_status}"}

        logger.info(f"Unhandled event type: {event['type']}")
        return {"status": "success", "message": f"Event received: {event['type']}"}

    except StripeServiceError as e:
        logger.error(f"Stripe webhook error for event {event_id if 'event_id' in locals() else 'unknown'}: {str(e)}")
        # Still return 200 to prevent Stripe retries for permanent failures
        return {"status": "error", "message": f"Webhook processing error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error processing webhook event {event_id if 'event_id' in locals() else 'unknown'}: {str(e)}")
        # Return 200 to prevent unnecessary retries for unexpected errors
        return {"status": "error", "message": "An unexpected error occurred"}


@router.delete(
    "/cancel",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionStatus,
    summary="Cancel a Stripe subscription",
)
async def cancel_subscription(
    cancel_at_period_end: bool = Query(
        True,
        description="Set to True to cancel at period request: CheckoutSessionRequest",
    ),
    user=Depends(auth_guard),
) -> SubscriptionStatus:
    """
    Cancel a Stripe subscription.

    - **cancel_at_period_end**: if True, the subscription remains active until period end.
    """
    try:
        user_id = user.get("sub")
        if cancel_at_period_end:
            # Schedule cancellation at period end
            sub = await stripe_service.cancel_user_subscription(
                user_id=user_id, cancel_at_period_end=True
            )
        else:
            # Cancel immediately
            sub = await stripe_service.cancel_user_subscription(
                user_id=user_id, cancel_at_period_end=False
            )

    except StripeServiceError as e:
        logger.error(f"Stripe service error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling subscription",
        )
    except Exception as e:
        logger.error(f"Unexpected error cancelling subscription: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )

    return SubscriptionStatus(
        status=sub.status,
        subscription_id=sub.id,
        cancel_at_period_end=sub.cancel_at_period_end
    )


@router.post(
    "/create-setup-intent",
    status_code=status.HTTP_200_OK,
    response_model=SetupIntentResponse,
    summary="Create Stripe Setup Intent",
    description="Create stripe setup intent to save user payment method for future transactions",
)
async def create_setup_intent(
    request: CheckoutSessionRequest, user=Depends(auth_guard)
) -> SetupIntentResponse:
    """
    Creates a SetupIntent to collect payment method for a customer.
    """
    user_id = user["sub"]

    if request.user_id != user_id:
        logger.warning(f"User ID mismatch: {request.user_id} vs {user.get('sub')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID in request does not match authenticated user",
        )

    try:
        # Check if user already has an active subscription
        has_subscription = await stripe_service.has_active_subscription(user_id=user_id)
        if has_subscription:
            logger.warning(f"User {user_id} already has an active subscription")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have an active subscription. Please manage your existing subscription instead.",
            )

        # retrieve stripe customer
        customer_id = await stripe_service.get_stripe_customer(user_id=user_id)

        # create stripe customer
        if not customer_id:
            customer_id = await stripe_service.create_stripe_customer(
                user_id=user_id, email=request.email
            )

        await stripe_service.update_stripe_user_subscription(
            customer=customer_id,
            subscription_data=SubscriptionUpdate(
                is_pro=True,
                plan=request.plan,
                stripe_subscription_id=None,
                subscription_start=None,
                subscription_end=None,
                trial_end_date=None
            )
        )

        # create ephemeral key for client side
        ephemeral_key = await stripe_service.create_ephemeral_key(
            user_id=user_id, customer_id=customer_id
        )

        # create sripe setup intent
        setup_intent_key = await stripe_service.create_setup_intent(
            user_id=user_id, customer_id=customer_id, plan=request.plan
        )
        return SetupIntentResponse(
            client_secret=setup_intent_key,
            ephemeral_key=ephemeral_key,
            customer_id=customer_id,
            publishable_key=settings.STRIPE_PUBLISHABLE_KEY or ""
        )

    except HTTPException as e:
        raise
    except Exception as e:
        logger.info(
            f"An unexpected error occured while creating setup intent: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Failed to create setup intent")


@router.post(
    "/create-customer-portal-session",
    status_code=status.HTTP_200_OK,
    response_model=BillingPortalResponse,
    summary="Stripe billing portal session",
    description="Create stripe billing portal session for customer",
)
async def create_customer_portal_session(
    request: Request, user=Depends(auth_guard)
) -> BillingPortalResponse:
    user_id = user.get("sub")

    customer_id = await stripe_service.get_stripe_customer(user_id=user_id)

    if not customer_id:
        raise HTTPException(status_code=400, detail="Customer not found.")

    try:
        portal_url = await stripe_service.create_customer_billing_portal(
            user_id=user_id, customer_id=customer_id
        )
        return BillingPortalResponse(url=portal_url)
    except Exception as e:
        logger.info(
            f"An unexpected error occured while creating billing portal session for user: {user_id} with error: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to create billing portal session"
        )


@router.get(
    "/subscription-status",
    status_code=status.HTTP_200_OK,
    summary="Get real-time subscription status",
    description="Get current subscription status from Stripe including payment failures",
)
async def get_subscription_status(
    user=Depends(auth_guard)
) -> Dict[str, Any]:
    """
    Get real-time subscription status including payment failure information.
    
    This endpoint checks Stripe directly for the most up-to-date subscription status,
    including whether the subscription is past due due to payment failures.
    """
    try:
        user_id = user.get("sub")
        
        # Get real-time status from Stripe
        subscription_status = await stripe_service.get_subscription_status(user_id)
        
        if not subscription_status:
            return {
                "has_subscription": False,
                "is_active": False,
                "status": "none",
                "message": "No active subscription found"
            }
        
        # Determine if subscription provides access
        has_access = subscription_status["active"] and not subscription_status["past_due"]
        
        # Create response with detailed status information
        response = {
            "has_subscription": True,
            "is_active": has_access,
            "status": subscription_status["status"],
            "subscription_id": subscription_status["subscription_id"],
            "past_due": subscription_status["past_due"],
            "cancel_at_period_end": subscription_status["cancel_at_period_end"],
            "current_period_end": subscription_status["current_period_end"],
        }
        
        # Add appropriate message based on status
        if subscription_status["past_due"]:
            response["message"] = "Subscription is past due. Please update your payment method."
            response["action_required"] = True
        elif subscription_status["cancel_at_period_end"]:
            response["message"] = "Subscription will cancel at the end of the billing period."
            response["action_required"] = False
        elif subscription_status["active"]:
            response["message"] = "Subscription is active and in good standing."
            response["action_required"] = False
        else:
            response["message"] = f"Subscription status: {subscription_status['status']}"
            response["action_required"] = False
            
        return response
        
    except StripeServiceError as e:
        logger.error(f"Stripe service error getting subscription status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving subscription status"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting subscription status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )
