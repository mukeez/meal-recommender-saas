"""Utility functions for file uploads to Supabase storage.

This module provides reusable functions for uploading files to Supabase storage buckets.
"""

import logging
from typing import Optional
import httpx
from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)


async def upload_file_to_bucket(
    file_content: bytes,
    file_path: str,
    content_type: str,
    bucket_name: str
) -> str:
    """Upload a file to Supabase storage bucket.

    Args:
        file_content: File content as bytes
        file_path: Path within the bucket (e.g., "user_id/avatar.png" or "user_id/meals/meal_123.jpg")
        content_type: MIME type of the file (e.g., "image/jpeg", "image/png")
        bucket_name: Name of the storage bucket

    Returns:
        Public URL to the uploaded file

    Raises:
        HTTPException: If there is an error uploading the file
    """
    logger.info(f"Uploading file to bucket '{bucket_name}': {file_path}")

    try:
        if not bucket_name:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Storage bucket name is required"
            )

        storage_url = f"{settings.SUPABASE_URL}/storage/v1/object/{bucket_name}/{file_path}"
        public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_path}"

        async with httpx.AsyncClient() as client:
            headers = {}
            if settings.SUPABASE_SERVICE_ROLE_KEY:
                headers["apikey"] = settings.SUPABASE_SERVICE_ROLE_KEY
                headers["Authorization"] = f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"
            headers["Content-Type"] = content_type

            response = await client.put(
                storage_url,
                headers=headers,
                content=file_content,
            )

            if response.status_code not in (200, 201, 204):
                error_detail = "Failed to upload file"
                try:
                    error_data = response.json()
                    if "message" in error_data:
                        error_detail = error_data["message"]
                except Exception:
                    pass

                logger.error(f"File upload failed: {error_detail}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload file: {error_detail}",
                )

            logger.info(f"File uploaded successfully: {public_url}")
            return public_url

    except httpx.RequestError as e:
        logger.error(f"Error communicating with storage service: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error communicating with storage service",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file",
        )


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

    # Additional validation could be added here for specific image types
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image type. Allowed types: {', '.join(allowed_types)}"
        )


def generate_meal_photo_path(user_id: str, meal_id: str, file_extension: str = "jpg") -> str:
    """Generate a standardized file path for meal photos.

    Args:
        user_id: ID of the user
        meal_id: ID of the meal
        file_extension: File extension (without dot)

    Returns:
        Standardized file path for the meal photo
    """
    return f"{user_id}/meals/{meal_id}.{file_extension}"


def generate_avatar_path(user_id: str, file_extension: str = "png") -> str:
    """Generate a standardized file path for user avatars.

    Args:
        user_id: ID of the user
        file_extension: File extension (without dot)

    Returns:
        Standardized file path for the user avatar
    """
    return f"{user_id}/avatar.{file_extension}" 