"""CloudWatch logging middleware for AWS CloudWatch Insights.

This middleware logs request details, response status codes, and exceptions
to AWS CloudWatch for monitoring and analysis.
"""

import json
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from collections import deque

import boto3
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)


class CloudWatchLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs requests to AWS CloudWatch.
    
    This middleware captures request details, processes them through the application,
    logs the response, and sends the log data to CloudWatch for monitoring and analysis.
    """

    def __init__(self, app, log_group_name: str = "meal-recommender-api", batch_size: int = 10, batch_timeout: int = 30):
        """Initialize the CloudWatch logging middleware.
        
        Args:
            app: FastAPI application instance
            log_group_name: CloudWatch log group name
            batch_size: Number of logs to batch before sending to CloudWatch
            batch_timeout: Timeout in seconds to send batched logs
        """
        super().__init__(app)
        self.log_group_name = log_group_name
        self.log_stream_name = f"api-logs-{datetime.now().strftime('%Y-%m-%d')}"
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.log_buffer: deque = deque()
        self.last_upload_time = time.time()
        self.cloudwatch_client = None
        self.sequence_token = None
        
        # Initialize CloudWatch client
        self._init_cloudwatch()

    def _init_cloudwatch(self):
        """Initialize CloudWatch client and create log group/stream if needed."""
        try:
            if not all([settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY]):
                logger.warning("AWS credentials not configured, CloudWatch logging disabled")
                return

            self.cloudwatch_client = boto3.client(
                'logs',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=getattr(settings, 'AWS_REGION', 'us-east-1')
            )

            # Create log group if it doesn't exist
            self._ensure_log_group_exists()
            
            # Create log stream
            self._create_log_stream()

        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch client: {e}")
            self.cloudwatch_client = None

    def _ensure_log_group_exists(self):
        """Ensure the CloudWatch log group exists."""
        if not self.cloudwatch_client:
            return
            
        try:
            self.cloudwatch_client.create_log_group(logGroupName=self.log_group_name)
            logger.info(f"Created CloudWatch log group: {self.log_group_name}")
        except Exception as e:
            # Check if it's a ResourceAlreadyExistsException (log group already exists)
            if 'ResourceAlreadyExistsException' in str(e):
                # Log group already exists, which is fine
                pass
            else:
                logger.error(f"Failed to create log group: {e}")

    def _create_log_stream(self):
        """Create a new log stream."""
        if not self.cloudwatch_client:
            return
            
        try:
            self.cloudwatch_client.create_log_stream(
                logGroupName=self.log_group_name,
                logStreamName=self.log_stream_name
            )
            logger.info(f"Created CloudWatch log stream: {self.log_stream_name}")
        except Exception as e:
            logger.error(f"Failed to create log stream: {e}")

    async def dispatch(self, request: Request, call_next):
        """Process the request and log details to CloudWatch.
        
        Args:
            request: The incoming HTTP request
            call_next: The next middleware or endpoint in the chain
            
        Returns:
            HTTP response
        """
        start_time = time.time()
        request_body = None
        
        # Safely read request body for logging
        try:
            request_body = await request.body()
        except Exception as e:
            logger.warning(f"Could not read request body: {e}")

        # Extract request headers
        headers = dict(request.headers)

        try:
            # Process the request
            response = await call_next(request)
            process_time = time.time() - start_time

            # Create log data
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "method": request.method,
                "endpoint": str(request.url),
                "params": self._parse_request_body(request_body),
                "headers": self._sanitize_headers(headers),
                "status_code": response.status_code,
                "process_time": round(process_time, 4),
                "user_agent": headers.get("user-agent"),
                "remote_addr": self._get_client_ip(request),
                "request_size": len(request_body) if request_body else 0,
                "response_size": self._get_response_size(response),
                "log_level": "INFO"
            }

            # Add to batch or send immediately
            await self._handle_log_upload(log_data)

            return response

        except HTTPException as exc:
            process_time = time.time() - start_time
            
            # Log HTTP exceptions
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "method": request.method,
                "endpoint": str(request.url),
                "params": self._parse_request_body(request_body),
                "headers": self._sanitize_headers(headers),
                "status_code": exc.status_code,
                "process_time": round(process_time, 4),
                "error": str(exc.detail),
                "error_type": "HTTPException",
                "user_agent": headers.get("user-agent"),
                "remote_addr": self._get_client_ip(request),
                "request_size": len(request_body) if request_body else 0,
                "log_level": "ERROR"
            }

            await self._handle_log_upload(log_data)

            logger.error(f"HTTPException: {exc.detail}")
            raise exc

        except Exception as e:
            process_time = time.time() - start_time
            
            # Log unhandled exceptions
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "method": request.method,
                "endpoint": str(request.url),
                "params": self._parse_request_body(request_body),
                "headers": self._sanitize_headers(headers),
                "status_code": 500,
                "process_time": round(process_time, 4),
                "error": str(e),
                "error_type": "UnhandledException",
                "user_agent": headers.get("user-agent"),
                "remote_addr": self._get_client_ip(request),
                "request_size": len(request_body) if request_body else 0,
                "log_level": "ERROR"
            }

            await self._handle_log_upload(log_data)

            logger.exception(f"Unhandled Exception: {e}")
            return Response(
                content="Internal Server Error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _parse_request_body(self, request_body: bytes | None) -> Dict[str, Any] | None:
        """Parse request body to JSON if possible and sanitize sensitive data.
        
        Args:
            request_body: Raw request body bytes
            
        Returns:
            Parsed and sanitized JSON data or None if not parseable
        """
        if not request_body:
            return None
            
        try:
            parsed_data = json.loads(request_body.decode('utf-8'))
            # Sanitize sensitive fields in the parsed data
            return self._sanitize_request_data(parsed_data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Return raw body as string if not JSON (but don't log actual content for security)
            try:
                raw_body = request_body.decode('utf-8', errors='ignore')
                # Check if raw body might contain sensitive data
                if self._contains_sensitive_data(raw_body):
                    return {"raw_body": "***SENSITIVE_DATA_MASKED***"}
                return {"raw_body": raw_body}
            except Exception:
                return {"raw_body": "<unparseable>"}

    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize headers by masking sensitive information.
        
        Args:
            headers: Request headers dictionary
            
        Returns:
            Sanitized headers with sensitive fields masked
        """
        sanitized = headers.copy()
        sensitive_headers = ['authorization', 'cookie', 'x-api-key', 'apikey']
        
        for header_name in sensitive_headers:
            if header_name in sanitized:
                sanitized[header_name] = '***MASKED***'
        
        return sanitized

    def _sanitize_request_data(self, data: Any) -> Any:
        """Recursively sanitize request data to mask sensitive fields.
        
        Args:
            data: Request data (dict, list, or other)
            
        Returns:
            Sanitized data with sensitive fields masked
        """
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if self._is_sensitive_field(key):
                    sanitized[key] = '***MASKED***'
                else:
                    sanitized[key] = self._sanitize_request_data(value)
            return sanitized
        elif isinstance(data, list):
            return [self._sanitize_request_data(item) for item in data]
        else:
            return data

    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if a field name indicates sensitive data.
        
        Args:
            field_name: Field name to check
            
        Returns:
            True if field contains sensitive data
        """
        field_lower = field_name.lower()
        sensitive_fields = [
            'password', 'passwd', 'pwd',
            'otp', 'otp_code', 'verification_code', 'verify_code',
            'token', 'access_token', 'refresh_token', 'auth_token',
            'secret', 'api_key', 'apikey', 'key',
            'credit_card', 'card_number', 'cvv', 'cvc',
            'ssn', 'social_security',
            'pin', 'passcode',
            'private_key', 'secret_key',
            'session_id', 'session_token'
        ]
        
        return any(sensitive in field_lower for sensitive in sensitive_fields)

    def _contains_sensitive_data(self, text: str) -> bool:
        """Check if raw text might contain sensitive data patterns.
        
        Args:
            text: Raw text to check
            
        Returns:
            True if text might contain sensitive data
        """
        text_lower = text.lower()
        sensitive_patterns = [
            'password', 'passwd', 'pwd',
            'otp', 'verification_code',
            'token', 'secret', 'key',
            'credit_card', 'card_number'
        ]
        
        return any(pattern in text_lower for pattern in sensitive_patterns)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request.
        
        Args:
            request: The HTTP request
            
        Returns:
            Client IP address
        """
        # Check for forwarded headers first (for load balancers/proxies)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
            
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
            
        # Fallback to direct client address
        if hasattr(request, "client") and request.client:
            return request.client.host
            
        return "unknown"

    def _get_response_size(self, response: Response) -> int:
        """Get response size from headers.
        
        Args:
            response: The HTTP response
            
        Returns:
            Response size in bytes, or 0 if unknown
        """
        content_length = response.headers.get("content-length")
        if content_length:
            try:
                return int(content_length)
            except ValueError:
                pass
        return 0

    async def _handle_log_upload(self, log_data: Dict[str, Any]) -> None:
        """Handle log upload to CloudWatch, either batched or immediate.
        
        Args:
            log_data: Log data dictionary to upload
        """
        if not self.cloudwatch_client:
            return

        current_time = time.time()

        # Add to buffer
        self.log_buffer.append(log_data)

        # Check if we should upload (batch size reached or timeout exceeded)
        should_upload = (
            len(self.log_buffer) >= self.batch_size or
            (current_time - self.last_upload_time) >= self.batch_timeout
        )

        if should_upload and self.log_buffer:
            # Create a copy of the buffer and clear it
            logs_to_upload = list(self.log_buffer)
            self.log_buffer.clear()
            self.last_upload_time = current_time

            # Upload logs in background (don't await to avoid blocking request)
            asyncio.create_task(self._upload_logs_background(logs_to_upload))

    async def _upload_logs_background(self, logs: List[Dict[str, Any]]) -> None:
        """Upload logs to CloudWatch in the background.
        
        Args:
            logs: List of log dictionaries to upload
        """
        try:
            if not self.cloudwatch_client:
                return

            # Check if we need to create a new log stream for a new day
            current_date = datetime.now().strftime('%Y-%m-%d')
            expected_stream_name = f"api-logs-{current_date}"
            
            if self.log_stream_name != expected_stream_name:
                # New day detected - create new log stream
                self.log_stream_name = expected_stream_name
                self.sequence_token = None  # Reset sequence token for new stream
                self._create_log_stream()
                logger.info(f"Created new daily log stream: {self.log_stream_name}")

            # Prepare log events for CloudWatch
            log_events = []
            for log_data in logs:
                log_events.append({
                    'timestamp': int(datetime.fromisoformat(log_data['timestamp'].replace('Z', '+00:00')).timestamp() * 1000),
                    'message': json.dumps(log_data)
                })

            # Sort by timestamp (CloudWatch requirement)
            log_events.sort(key=lambda x: x['timestamp'])

            # Prepare put_log_events parameters
            put_params = {
                'logGroupName': self.log_group_name,
                'logStreamName': self.log_stream_name,
                'logEvents': log_events
            }

            # Add sequence token if we have one
            if self.sequence_token:
                put_params['sequenceToken'] = self.sequence_token

            # Send to CloudWatch
            response = self.cloudwatch_client.put_log_events(**put_params)
            
            # Update sequence token for next batch
            self.sequence_token = response.get('nextSequenceToken')
            
            logger.debug(f"Sent {len(logs)} log events to CloudWatch")

        except Exception as e:
            logger.error(f"Failed to upload logs to CloudWatch: {e}")

    async def flush_logs(self) -> None:
        """Manually flush any remaining logs in the buffer.
        
        This can be called during application shutdown to ensure all logs are uploaded.
        """
        if self.log_buffer:
            logs_to_upload = list(self.log_buffer)
            self.log_buffer.clear()
            
            try:
                await self._upload_logs_background(logs_to_upload)
                logger.info(f"Flushed {len(logs_to_upload)} remaining logs to CloudWatch")
            except Exception as e:
                logger.error(f"Failed to flush logs to CloudWatch: {e}") 