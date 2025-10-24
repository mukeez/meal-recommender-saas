import pytest
from app.services.cache_service import cache_service


class TestCacheService:
    """Test suite for CacheService unified cache key generation."""

    def test_generate_unified_cache_key_basic(self):
        """Test basic unified cache key generation."""
        key = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            user_id="user123",
            view_type="map"
        )
        
        assert "restaurant_search:map" in key
        assert "51.507" in key
        assert "-0.128" in key
        assert "5.0" in key

    def test_generate_unified_cache_key_with_query(self):
        """Test cache key generation with search query."""
        key1 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            query="pizza",
            user_id="user123"
        )
        
        key2 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            query="pizza",
            user_id="user123"
        )
        
        # Same query should produce same key
        assert key1 == key2

    def test_generate_unified_cache_key_different_queries(self):
        """Test that different queries produce different keys."""
        key1 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            query="pizza",
            user_id="user123"
        )
        
        key2 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            query="burger",
            user_id="user123"
        )
        
        assert key1 != key2

    def test_generate_unified_cache_key_with_cuisines(self):
        """Test cache key generation with cuisine filters."""
        key = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            cuisines=["italian", "mexican"],
            user_id="user123"
        )
        
        assert "restaurant_search" in key

    def test_generate_unified_cache_key_cuisines_order_independent(self):
        """Test that cuisine order doesn't affect cache key."""
        key1 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            cuisines=["italian", "mexican"],
            user_id="user123"
        )
        
        key2 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            cuisines=["mexican", "italian"],
            user_id="user123"
        )
        
        # Should produce same key (sorted internally)
        assert key1 == key2

    def test_generate_unified_cache_key_with_dietary_restrictions(self):
        """Test cache key generation with dietary restrictions."""
        key = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            dietary_restrictions=["vegan", "gluten_free"],
            user_id="user123"
        )
        
        assert "restaurant_search" in key

    def test_generate_unified_cache_key_restrictions_order_independent(self):
        """Test that dietary restrictions order doesn't affect cache key."""
        key1 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            dietary_restrictions=["vegan", "gluten_free"],
            user_id="user123"
        )
        
        key2 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            dietary_restrictions=["gluten_free", "vegan"],
            user_id="user123"
        )
        
        assert key1 == key2

    def test_generate_unified_cache_key_case_insensitive(self):
        """Test that query case doesn't affect cache key."""
        key1 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            query="Pizza",
            user_id="user123"
        )
        
        key2 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            query="pizza",
            user_id="user123"
        )
        
        # Should normalize to lowercase
        assert key1 == key2

    def test_generate_unified_cache_key_different_users(self):
        """Test that different users get different cache keys."""
        key1 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            query="pizza",
            user_id="user123"
        )
        
        key2 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            query="pizza",
            user_id="user456"
        )
        
        assert key1 != key2

    def test_generate_unified_cache_key_different_view_types(self):
        """Test that different view types produce different keys."""
        key1 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            user_id="user123",
            view_type="map"
        )
        
        key2 = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            user_id="user123",
            view_type="list"
        )
        
        assert key1 != key2
        assert ":map:" in key1
        assert ":list:" in key2

    def test_generate_unified_cache_key_coordinate_rounding(self):
        """Test that coordinates are rounded consistently."""
        key1 = cache_service.generate_unified_cache_key(
            latitude=51.50741234,
            longitude=-0.12781234,
            radius=5.0,
            user_id="user123"
        )
        
        key2 = cache_service.generate_unified_cache_key(
            latitude=51.50749999,
            longitude=-0.12789999,
            radius=5.0,
            user_id="user123"
        )
        
        # Should round to same value (3 decimals)
        assert key1 == key2

    def test_generate_unified_cache_key_with_all_filters(self):
        """Test cache key generation with all filter parameters."""
        key = cache_service.generate_unified_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            query="pizza",
            meal_name="margherita",
            restaurant_name="Bella Italia",
            cuisines=["italian"],
            dietary_restrictions=["vegan"],
            dietary_preference="vegetarian",
            user_id="user123",
            view_type="map"
        )
        
        assert "restaurant_search:map" in key
        assert isinstance(key, str)
        assert len(key) > 0

    def test_generate_cache_key_legacy(self):
        """Test legacy cache key generation still works."""
        filters = {
            "query": "pizza",
            "calories": 600,
            "user_id": "user123"
        }
        
        key = cache_service.generate_cache_key(
            latitude=51.5074,
            longitude=-0.1278,
            radius=5.0,
            filters=filters
        )
        
        assert "map_pins" in key
        assert "51.507" in key
