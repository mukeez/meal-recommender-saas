"""Utility functions for file uploads to S3 storage.

This module provides reusable functions for uploading files to AWS S3 buckets.
"""

import logging
from typing import Optional
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)


async def upload_file_to_s3(
    file_content: bytes,
    file_path: str,
    content_type: str,
) -> str:
    """Upload a file to S3 bucket.

    Args:
        file_content: File content as bytes
        file_path: Path within the bucket (e.g., "avatars/user_id/avatar.png" or "meals/user_id/meal_123.jpg")
        content_type: MIME type of the file (e.g., "image/jpeg", "image/png")

    Returns:
        Public URL to the uploaded file

    Raises:
        HTTPException: If there is an error uploading the file
    """
    logger.info(f"Uploading file to S3 bucket '{settings.S3_MEDIA_NAME}': {file_path}")

    try:
        if not settings.S3_MEDIA_NAME:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="S3 media bucket name is not configured"
            )

        if not all([settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY, settings.AWS_REGION]):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AWS credentials are not properly configured"
            )

        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )

        # Upload file to S3
        s3_client.put_object(
            Bucket=settings.S3_MEDIA_NAME,
            Key=file_path,
            Body=file_content,
            ContentType=content_type
        )

        # Generate public URL
        public_url = f"https://{settings.S3_MEDIA_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{file_path}"
        
        logger.info(f"File uploaded successfully to S3: {public_url}")
        return public_url

    except NoCredentialsError:
        logger.error("AWS credentials not found")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AWS credentials not configured properly",
        )
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"S3 upload failed: {error_code} - {error_message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to S3: {error_message}",
        )
    except Exception as e:
        logger.error(f"Unexpected error uploading file to S3: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file",
        )


# Legacy function for backward compatibility - redirects to S3
async def upload_file_to_bucket(
    file_content: bytes,
    file_path: str,
    content_type: str,
    bucket_name: Optional[str] = None
) -> str:
    """Legacy function that redirects to S3 upload.
    
    Args:
        file_content: File content as bytes
        file_path: Path within the bucket
        content_type: MIME type of the file
        bucket_name: Ignored (uses S3_MEDIA_NAME from settings)

    Returns:
        Public URL to the uploaded file
    """
    return await upload_file_to_s3(file_content, file_path, content_type)


def validate_image_file(filename: Optional[str], content_type: Optional[str]) -> None:
    """Validate that the uploaded file is a valid image.

    Args:
        filename: Name of the uploaded file
        content_type: MIME type of the uploaded file

    Raises:
        HTTPException: If the file is not a valid image
    """
    if not content_type or not content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed"
        )

    # Additional validation for specific image types
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type. Allowed types: {', '.join(allowed_types)}"
        )


def generate_meal_photo_path(user_id: str, meal_id: str, file_extension: str = "jpg") -> str:
    """Generate a standardized S3 path for meal photos.

    Args:
        user_id: ID of the user
        meal_id: ID of the meal
        file_extension: File extension (without dot)

    Returns:
        Standardized S3 path for the meal photo: {env}/meals/{user_id}/{meal_id}.{ext}
    """
    env_prefix = "prod" if settings.ENVIRONMENT == "production" else "dev"
    return f"{env_prefix}/meals/{user_id}/{meal_id}.{file_extension}"


def generate_avatar_path(user_id: str, file_extension: str = "png") -> str:
    """Generate a standardized S3 path for user avatars.

    Args:
        user_id: ID of the user
        file_extension: File extension (without dot)

    Returns:
        Standardized S3 path for the user avatar: {env}/avatars/{user_id}/avatar.{ext}
    """
    env_prefix = "prod" if settings.ENVIRONMENT == "production" else "dev"
    return f"{env_prefix}/avatars/{user_id}/avatar.{file_extension}" 