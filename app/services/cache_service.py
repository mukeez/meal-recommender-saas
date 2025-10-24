"""Redis caching service for map pins and other data.


This module provides caching functionality to reduce API calls
and improve performance.
"""

import logging
import json
import hashlib
from typing import Optional, Any, Dict, List
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Service for caching data in Redis."""
    
    def __init__(self):
        """Initialize Redis connection pool."""
        if settings.GOOGLE_PLACES_CACHE_ENABLED:
            try:
                self.pool = ConnectionPool.from_url(
                    f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}",
                    max_connections=20,
                    decode_responses=True
                )
                self.redis_client = Redis(connection_pool=self.pool)
                logger.info("Redis cache initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis: {e}. Caching disabled.")
                self.redis_client = None
        else:
            logger.info("Caching disabled by configuration")
            self.redis_client = None
        
        # Cache TTL in seconds (24 hours default)
        self.ttl = settings.GOOGLE_PLACES_CACHE_TTL_HOURS * 3600
    
    def generate_cache_key(
        self,
        latitude: float,
        longitude: float,
        radius: float,
        filters: Dict[str, Any]
    ) -> str:
        """Generate deterministic cache key from parameters.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            radius: Search radius in km
            filters: Dictionary of filter parameters
            
        Returns:
            Cache key string
        """
        # Round coordinates to 3 decimals (~110m precision)
        lat_rounded = round(latitude, 3)
        lng_rounded = round(longitude, 3)
        radius_rounded = round(radius, 1)
        
        # Create a deterministic string from filters
        filter_str = json.dumps(filters, sort_keys=True)
        filter_hash = hashlib.md5(filter_str.encode()).hexdigest()[:8]
        
        return f"map_pins:{lat_rounded}:{lng_rounded}:{radius_rounded}:{filter_hash}"
    
    def generate_unified_cache_key(
        self,
        latitude: float,
        longitude: float,
        radius: float,
        query: Optional[str] = None,
        meal_name: Optional[str] = None,
        restaurant_name: Optional[str] = None,
        cuisines: Optional[List[str]] = None,
        dietary_restrictions: Optional[List[str]] = None,
        dietary_preference: Optional[str] = None,
        user_id: Optional[str] = None,
        view_type: str = "map"
    ) -> str:
        """Generate unified cache key from normalized filters.
        
        This ensures that the same filters produce the same cache key
        across both List and Map views for consistency.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            radius: Search radius in km
            query: General search term
            meal_name: Meal name search
            restaurant_name: Restaurant name search
            cuisines: List of cuisine types (will be sorted for consistency)
            dietary_restrictions: List of restrictions (will be sorted)
            dietary_preference: Dietary preference string
            user_id: User ID for per-user caching
            view_type: "map" or "list"
            
        Returns:
            Cache key string
        """
        # Round coordinates for consistency
        lat_rounded = round(latitude, 3)
        lng_rounded = round(longitude, 3)
        radius_rounded = round(radius, 1)
        
        # Build normalized filter dict (sorted for deterministic hashing)
        filter_dict = {
            "query": query.lower().strip() if query else None,
            "meal_name": meal_name.lower().strip() if meal_name else None,
            "restaurant_name": restaurant_name.lower().strip() if restaurant_name else None,
            "cuisines": sorted([c.lower() for c in cuisines]) if cuisines else None,
            "dietary_restrictions": sorted([d.lower() for d in dietary_restrictions]) if dietary_restrictions else None,
            "dietary_preference": dietary_preference.lower().strip() if dietary_preference else None,
            "user_id": user_id
        }
        
        # Remove None values for cleaner hash
        filter_dict = {k: v for k, v in filter_dict.items() if v is not None}
        
        # Create deterministic hash from filters
        filter_str = json.dumps(filter_dict, sort_keys=True)
        filter_hash = hashlib.md5(filter_str.encode()).hexdigest()[:12]
        
        cache_key = f"restaurant_search:{view_type}:{lat_rounded}:{lng_rounded}:{radius_rounded}:{filter_hash}"
        
        logger.debug(f"Generated cache key: {cache_key}")
        return cache_key
    
    async def get_cached_map_pins(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached map pins data.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached data or None if not found/expired
        """
        if not self.redis_client:
            return None
        
        try:
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                logger.info(f"Cache HIT for key: {cache_key}")
                return json.loads(cached_data)
            else:
                logger.info(f"Cache MISS for key: {cache_key}")
                return None
                
        except RedisError as e:
            logger.warning(f"Redis error during get: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode cached data: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting cache: {e}")
            return None
    
    async def set_cached_map_pins(
        self,
        cache_key: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Store map pins data in cache.
        
        Args:
            cache_key: Cache key
            data: Data to cache
            ttl: Time to live in seconds (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            ttl_seconds = ttl or self.ttl
            serialized_data = json.dumps(data)
            
            await self.redis_client.setex(
                cache_key,
                ttl_seconds,
                serialized_data
            )
            
            logger.info(f"Cached data with key: {cache_key}, TTL: {ttl_seconds}s")
            return True
            
        except RedisError as e:
            logger.warning(f"Redis error during set: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error setting cache: {e}")
            return False
    
    async def invalidate_cache(self, cache_key: str) -> bool:
        """Invalidate a cache entry.
        
        Args:
            cache_key: Cache key to invalidate
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.delete(cache_key)
            logger.info(f"Invalidated cache key: {cache_key}")
            return True
        except RedisError as e:
            logger.warning(f"Redis error during delete: {e}")
            return False
    
    async def clear_all(self) -> bool:
        """Clear all cache entries in Redis.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            logger.info("Redis client not initialized, nothing to clear")
            return False
        
        try:
            await self.redis_client.flushdb()
            logger.info("Successfully cleared all cache entries from Redis")
            return True
        except RedisError as e:
            logger.warning(f"Redis error during flushdb: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error clearing cache: {e}")
            return False
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            await self.pool.disconnect()
            logger.info("Redis connection closed")


cache_service = CacheService()
