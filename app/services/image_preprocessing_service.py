"""Image preprocessing service for meal recommendation API.

This service handles image preprocessing operations including validation,
resizing, normalization, and optimization for better ML model performance.
"""

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import io
import logging
from typing import Optional, Tuple, Union
import warnings

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class ImagePreprocessingService:
    """Service for preprocessing images before analysis."""
    
    def __init__(self, target_size=(512, 512), min_resolution=64, max_file_size_mb=10):
        """Initialize the image preprocessing service.
        
        Args:
            target_size: Target size for image resizing (width, height)
            min_resolution: Minimum acceptable resolution
            max_file_size_mb: Maximum file size in MB
        """
        self.target_size = target_size
        self.min_resolution = min_resolution
        self.max_file_size_mb = max_file_size_mb
        self.logger = logging.getLogger(__name__)
        
    def preprocess_image(self, image_bytes: bytes) -> Optional[bytes]:
        """Main preprocessing pipeline for food images.
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Preprocessed image bytes or None if preprocessing fails
        """
        try:
            # Validate image
            if not self._validate_image(image_bytes):
                return None
                
            # Load and convert image
            image = Image.open(io.BytesIO(image_bytes))
            
            # Apply preprocessing steps
            image = self._ensure_rgb(image)
            image = self._resize_with_aspect_ratio(image)
            image = self._enhance_image_quality(image)
            image = self._normalize_for_analysis(image)
            
            # Convert back to bytes
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=95, optimize=True)
            preprocessed_bytes = output.getvalue()
            
            self.logger.info(f"Image preprocessing successful: {len(image_bytes)} -> {len(preprocessed_bytes)} bytes")
            return preprocessed_bytes
            
        except Exception as e:
            self.logger.error(f"Image preprocessing failed: {e}")
            return None
    
    def _validate_image(self, image_bytes: bytes) -> bool:
        """Validate image format, size, and basic properties.
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            True if image is valid, False otherwise
        """
        try:
            # Check file size
            size_mb = len(image_bytes) / (1024 * 1024)
            if size_mb > self.max_file_size_mb:
                self.logger.warning(f"Image too large: {size_mb:.2f}MB > {self.max_file_size_mb}MB")
                return False
            
            # Check if it's a valid image
            image = Image.open(io.BytesIO(image_bytes))
            
            # Check resolution
            width, height = image.size
            if width < self.min_resolution or height < self.min_resolution:
                self.logger.warning(f"Image resolution too low: {width}x{height}")
                return False
            
            # Check if image is not corrupted
            image.verify()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Image validation failed: {e}")
            return False
    
    def _ensure_rgb(self, image: Image.Image) -> Image.Image:
        """Convert image to RGB format if needed.
        
        Args:
            image: PIL Image
            
        Returns:
            RGB PIL Image
        """
        if image.mode != 'RGB':
            if image.mode == 'RGBA':
                # Create white background for transparent images
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                return background
            else:
                return image.convert('RGB')
        return image
    
    def _resize_with_aspect_ratio(self, image: Image.Image) -> Image.Image:
        """Resize image maintaining aspect ratio with center crop.
        
        Args:
            image: PIL Image
            
        Returns:
            Resized PIL Image
        """
        original_size = image.size
        target_width, target_height = self.target_size
        
        # Calculate scale to fit the smaller dimension
        scale = max(target_width / original_size[0], target_height / original_size[1])
        
        # Resize maintaining aspect ratio
        new_size = (int(original_size[0] * scale), int(original_size[1] * scale))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Center crop to exact target size
        left = (new_size[0] - target_width) // 2
        top = (new_size[1] - target_height) // 2
        right = left + target_width
        bottom = top + target_height
        
        image = image.crop((left, top, right, bottom))
        return image
    
    def _enhance_image_quality(self, image: Image.Image) -> Image.Image:
        """Enhance image quality for better analysis.
        
        Args:
            image: PIL Image
            
        Returns:
            Enhanced PIL Image
        """
        try:
            # Enhance contrast slightly
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.1)
            
            # Enhance sharpness slightly
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.1)
            
            # Apply subtle noise reduction
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            return image
            
        except Exception as e:
            self.logger.warning(f"Image enhancement failed, using original: {e}")
            return image
    
    def _normalize_for_analysis(self, image: Image.Image) -> Image.Image:
        """Normalize image for consistent analysis.
        
        Args:
            image: PIL Image
            
        Returns:
            Normalized PIL Image
        """
        try:
            # Convert to numpy array for processing
            img_array = np.array(image, dtype=np.float32)
            
            # Normalize to [0, 1]
            img_array = img_array / 255.0
            
            # Apply standard normalization (optional, depends on model requirements)
            # For now, we'll keep it simple and just ensure consistent range
            
            # Convert back to [0, 255] range
            img_array = (img_array * 255.0).astype(np.uint8)
            
            return Image.fromarray(img_array)
            
        except Exception as e:
            self.logger.warning(f"Image normalization failed, using original: {e}")
            return image
    
    def get_image_info(self, image_bytes: bytes) -> dict:
        """Get information about an image.
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Dictionary with image information
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            
            return {
                "format": image.format,
                "mode": image.mode,
                "size": image.size,
                "file_size_mb": len(image_bytes) / (1024 * 1024),
                "has_transparency": image.mode in ('RGBA', 'LA') or 'transparency' in image.info
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get image info: {e}")
            return {}
    
    def preprocess_batch(self, image_bytes_list: list) -> list:
        """Process a batch of images.
        
        Args:
            image_bytes_list: List of image bytes
            
        Returns:
            List of preprocessed image bytes
        """
        processed_images = []
        
        for i, image_bytes in enumerate(image_bytes_list):
            processed_image = self.preprocess_image(image_bytes)
            processed_images.append(processed_image)
            
            if (i + 1) % 10 == 0:
                self.logger.info(f"Processed {i + 1}/{len(image_bytes_list)} images")
        
        return processed_images


image_preprocessing_service = ImagePreprocessingService()