"""Embedding generation service using Replicate CLIP model.

This module provides functionality to generate embeddings for images using
Replicate's CLIP model API instead of local Sentence Transformers.
"""

import os
import base64
import logging
import replicate
import numpy as np
from typing import Optional, List
from PIL import Image
import io

logger = logging.getLogger(__name__)


class ReplicateEmbeddingGenerator:
    """Generate embeddings using Replicate CLIP model."""
    
    def __init__(self, api_token: Optional[str] = None):
        """Initialize the Replicate embedding generator.
        
        Args:
            api_token: Replicate API token, defaults to environment variable
        """
        self.api_token = api_token or os.environ.get("REPLICATE_API_TOKEN")
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN environment variable or api_token parameter is required")
        
        self.client = replicate.Client(api_token=self.api_token)
        self.model_name = "krthr/clip-embeddings:1c0371070cb827ec3c7f2f28adcdde54b50dcd239aa6faea0bc98b174ef03fb4"
        self.embedding_dim = 768  # CLIP embedding dimension
        
        logger.info(f"Initialized Replicate embedding generator with model: {self.model_name}")
    
    def generate_embedding(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """Generate embedding for a single image using Replicate CLIP.
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Normalized embedding vector as numpy array, or None if failed
        """
        try:
            # Convert image bytes to base64 data URI
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Determine MIME type (default to JPEG if uncertain)
            try:
                image = Image.open(io.BytesIO(image_bytes))
                if image.format == 'PNG':
                    mime_type = "image/png"
                elif image.format == 'JPEG':
                    mime_type = "image/jpeg"
                elif image.format == 'WEBP':
                    mime_type = "image/webp"
                else:
                    mime_type = "image/jpeg"  # Default fallback
            except Exception:
                mime_type = "image/jpeg"  # Default fallback
            
            data_uri = f'data:{mime_type};base64,{image_b64}'
            
            # Generate embedding using Replicate
            logger.debug(f"Generating embedding for image with MIME type: {mime_type}")
            output = self.client.run(
                self.model_name,
                input={"image": data_uri}
            )
            
            if not output or "embedding" not in output:
                logger.error("No embedding returned from Replicate API")
                return None
            
            # Convert to numpy array and normalize
            embedding = np.array(output["embedding"], dtype=np.float32)
            
            # Normalize the embedding vector
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            
            logger.debug(f"Successfully generated embedding with dimension: {len(embedding)}")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            return None
    
    def generate_batch_embeddings(self, images_bytes: List[bytes], max_concurrent: int = 5) -> List[Optional[np.ndarray]]:
        """Generate embeddings for multiple images.
        
        Args:
            images_bytes: List of image bytes
            max_concurrent: Maximum concurrent requests (not used with current implementation)
            
        Returns:
            List of embedding vectors, with None for failed generations
        """
        embeddings = []
        
        for i, image_bytes in enumerate(images_bytes):
            logger.info(f"Processing image {i+1}/{len(images_bytes)}")
            
            embedding = self.generate_embedding(image_bytes)
            embeddings.append(embedding)
            
            # Add small delay to avoid rate limiting
            if i < len(images_bytes) - 1:  # Don't sleep after the last image
                import time
                time.sleep(0.5)  # 500ms delay between requests
        
        successful_count = sum(1 for emb in embeddings if emb is not None)
        logger.info(f"Successfully generated {successful_count}/{len(images_bytes)} embeddings")
        
        return embeddings
    
    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension.
        
        Returns:
            Embedding dimension (768 for CLIP)
        """
        return self.embedding_dim


# Global instance for easy import
embedding_generator = ReplicateEmbeddingGenerator()