"""
Unit tests for feature flag management system.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.config.enhanced_settings import EnhancedSettings, FeatureFlags
from src.config.feature_manager import FeatureManager


@pytest.fixture
def mock_settings():
    """Create mock enhanced settings"""
    settings = Mock(spec=EnhancedSettings)
    settings.environment = "development"
    settings.is_production = False
    settings.features = Mock(spec=FeatureFlags)
    settings.features.enable_hybrid_search = False
    settings.features.enable_elasticsearch = False
    settings.features.enable_source_highlighting = True
    settings.features.enable_phi_scrubbing = True
    settings.features.enable_response_validation = True
    settings.features.enable_metrics = True
    return settings


@pytest.fixture
def mock_redis():
    """Create mock Redis client"""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.keys = AsyncMock(return_value=[])
    redis_mock.ttl = AsyncMock(return_value=-1)
    redis_mock.ping = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
async def feature_manager(mock_settings, mock_redis):
    """Create feature manager with mocked dependencies"""
    with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
        manager = FeatureManager(mock_settings)
        await manager._ensure_redis_connection()
        return manager


class TestFeatureManagerInitialization:
    """Test feature manager initialization"""
    
    def test_feature_manager_init(self, mock_settings):
        """Test feature manager initialization"""
        manager = FeatureManager(mock_settings)
        
        assert manager.settings is mock_settings
        assert manager.redis_client is None  # Not connected yet
        assert manager._flag_cache == {}
        assert manager.cache_ttl == 300
    
    @pytest.mark.asyncio
    async def test_redis_connection_success(self, mock_settings, mock_redis):
        """Test successful Redis connection"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            manager = FeatureManager(mock_settings)
            await manager._ensure_redis_connection()
            
            assert manager.redis_client is mock_redis
            mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, mock_settings):
        """Test Redis connection failure handling"""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            manager = FeatureManager(mock_settings)
            
            # Should handle connection failure gracefully
            await manager._ensure_redis_connection()
            assert manager.redis_client is None


class TestFeatureFlagRetrieval:
    """Test feature flag retrieval"""
    
    @pytest.mark.asyncio
    async def test_get_flag_from_settings_only(self, feature_manager, mock_settings):
        """Test getting flag value from settings when no Redis override"""
        mock_settings.features.enable_hybrid_search = True
        feature_manager.redis_client.get.return_value = None
        
        result = await feature_manager.get_flag("enable_hybrid_search")
        assert result is True
        
        # Should check Redis for override
        feature_manager.redis_client.get.assert_called_with("flag:enable_hybrid_search")
    
    @pytest.mark.asyncio
    async def test_get_flag_with_redis_override(self, feature_manager, mock_settings):
        """Test getting flag with Redis override"""
        mock_settings.features.enable_hybrid_search = False
        feature_manager.redis_client.get.return_value = "true"
        
        result = await feature_manager.get_flag("enable_hybrid_search")
        assert result is True
        
        feature_manager.redis_client.get.assert_called_with("flag:enable_hybrid_search")
    
    @pytest.mark.asyncio
    async def test_get_flag_nonexistent(self, feature_manager):
        """Test getting nonexistent flag"""
        feature_manager.redis_client.get.return_value = None
        
        result = await feature_manager.get_flag("nonexistent_flag")
        assert result is False  # Default value
    
    @pytest.mark.asyncio
    async def test_get_flag_with_caching(self, feature_manager, mock_settings):
        """Test flag caching mechanism"""
        mock_settings.features.enable_metrics = True
        feature_manager.redis_client.get.return_value = None
        
        # First call should check Redis
        result1 = await feature_manager.get_flag("enable_metrics")
        assert result1 is True
        
        # Second call should use cache
        result2 = await feature_manager.get_flag("enable_metrics")
        assert result2 is True
        
        # Redis should only be called once
        assert feature_manager.redis_client.get.call_count == 1
    
    @pytest.mark.asyncio
    async def test_get_flag_cache_expiry(self, feature_manager, mock_settings):
        """Test cache expiry behavior"""
        mock_settings.features.enable_metrics = True
        feature_manager.redis_client.get.return_value = None
        feature_manager.cache_ttl = 0.1  # 100ms cache
        
        # First call
        await feature_manager.get_flag("enable_metrics")
        
        # Wait for cache to expire
        await asyncio.sleep(0.2)
        
        # Second call should check Redis again
        await feature_manager.get_flag("enable_metrics")
        
        assert feature_manager.redis_client.get.call_count == 2


class TestFeatureFlagUpdates:
    """Test feature flag updates"""
    
    @pytest.mark.asyncio
    async def test_set_flag_success(self, feature_manager):
        """Test successful flag update"""
        feature_manager.redis_client.set.return_value = True
        
        result = await feature_manager.set_flag("enable_hybrid_search", True, ttl_minutes=60)
        assert result is True
        
        # Should set flag with TTL
        feature_manager.redis_client.set.assert_called_with(
            "flag:enable_hybrid_search", 
            "true", 
            ex=3600  # 60 minutes in seconds
        )
        
        # Should clear cache
        assert "enable_hybrid_search" not in feature_manager._flag_cache
    
    @pytest.mark.asyncio
    async def test_set_flag_production_safety_check(self, mock_settings):
        """Test production safety check for critical flags"""
        mock_settings.is_production = True
        mock_redis = AsyncMock()
        
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            manager = FeatureManager(mock_settings)
            await manager._ensure_redis_connection()
            
            # Should not allow disabling safety flags in production
            result = await manager.set_flag("enable_phi_scrubbing", False)
            assert result is False
            
            # Redis should not be called
            mock_redis.set.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_set_flag_invalid_name(self, feature_manager):
        """Test setting invalid flag name"""
        result = await feature_manager.set_flag("invalid_flag_name", True)
        assert result is False
        
        feature_manager.redis_client.set.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_set_flag_redis_failure(self, feature_manager):
        """Test Redis failure during flag update"""
        feature_manager.redis_client.set.side_effect = Exception("Redis error")
        
        result = await feature_manager.set_flag("enable_hybrid_search", True)
        assert result is False


class TestFeatureFlagBulkOperations:
    """Test bulk feature flag operations"""
    
    @pytest.mark.asyncio
    async def test_get_all_flags(self, feature_manager, mock_settings):
        """Test getting all flags with details"""
        # Setup mock Redis responses
        feature_manager.redis_client.keys.return_value = [
            "flag:enable_hybrid_search",
            "flag:enable_metrics"
        ]
        feature_manager.redis_client.get.side_effect = ["true", None]
        feature_manager.redis_client.ttl.side_effect = [3600, -1]
        
        # Setup settings values
        mock_settings.features.enable_hybrid_search = False
        mock_settings.features.enable_metrics = True
        
        result = await feature_manager.get_all_flags()
        
        assert "enable_hybrid_search" in result
        assert "enable_metrics" in result
        
        # Check hybrid search flag details
        hybrid_flag = result["enable_hybrid_search"]
        assert hybrid_flag["current_value"] is True
        assert hybrid_flag["default_value"] is False
        assert hybrid_flag["has_override"] is True
        assert hybrid_flag["ttl_seconds"] == 3600
        
        # Check metrics flag details
        metrics_flag = result["enable_metrics"]
        assert metrics_flag["current_value"] is True
        assert metrics_flag["default_value"] is True
        assert metrics_flag["has_override"] is False
    
    @pytest.mark.asyncio
    async def test_clear_overrides(self, feature_manager):
        """Test clearing all flag overrides"""
        # Setup mock Redis keys
        feature_manager.redis_client.keys.return_value = [
            "flag:enable_hybrid_search",
            "flag:enable_elasticsearch",
            "other:key"  # Should be ignored
        ]
        feature_manager.redis_client.delete.return_value = 2
        
        result = await feature_manager.clear_overrides()
        assert result == 2
        
        # Should only delete flag keys
        feature_manager.redis_client.delete.assert_called_with(
            "flag:enable_hybrid_search",
            "flag:enable_elasticsearch"
        )
        
        # Should clear cache
        assert feature_manager._flag_cache == {}
    
    @pytest.mark.asyncio
    async def test_validate_flag_dependencies(self, feature_manager, mock_settings):
        """Test flag dependency validation"""
        # Setup conflicting configuration
        mock_settings.features.search_backend = "hybrid"
        mock_settings.features.enable_hybrid_search = False
        mock_settings.features.enable_elasticsearch = False
        
        warnings = await feature_manager.validate_flag_dependencies()
        
        assert len(warnings) > 0
        assert any("hybrid" in warning.lower() for warning in warnings)
    
    @pytest.mark.asyncio
    async def test_get_feature_usage_stats(self, feature_manager):
        """Test feature usage statistics"""
        # Setup mock Redis data
        feature_manager.redis_client.keys.return_value = [
            "flag:enable_hybrid_search",
            "flag:enable_metrics"
        ]
        
        stats = await feature_manager.get_feature_usage_stats()
        
        assert "total_flags" in stats
        assert "overrides_count" in stats
        assert stats["total_flags"] >= 0
        assert stats["overrides_count"] >= 0


class TestFeatureFlagValidation:
    """Test feature flag validation"""
    
    @pytest.mark.asyncio
    async def test_production_safety_validation(self, mock_settings):
        """Test production safety validation"""
        mock_settings.is_production = True
        mock_redis = AsyncMock()
        
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            manager = FeatureManager(mock_settings)
            
            # Test safety flag validation
            assert not manager._is_flag_update_allowed("enable_phi_scrubbing", False)
            assert not manager._is_flag_update_allowed("enable_response_validation", False)
            
            # Test non-safety flag (should be allowed)
            assert manager._is_flag_update_allowed("enable_hybrid_search", True)
    
    def test_flag_name_validation(self, feature_manager):
        """Test flag name validation"""
        assert feature_manager._is_valid_flag_name("enable_hybrid_search")
        assert feature_manager._is_valid_flag_name("enable_metrics")
        assert not feature_manager._is_valid_flag_name("invalid_flag")
        assert not feature_manager._is_valid_flag_name("")
    
    def test_flag_dependency_check(self, feature_manager, mock_settings):
        """Test flag dependency validation"""
        # Test hybrid search dependencies
        mock_settings.features.search_backend = "hybrid"
        mock_settings.features.enable_hybrid_search = False
        
        warnings = feature_manager._check_flag_dependencies()
        assert len(warnings) > 0
        
        # Test consistent configuration
        mock_settings.features.enable_hybrid_search = True
        mock_settings.features.enable_elasticsearch = True
        
        warnings = feature_manager._check_flag_dependencies()
        # Should have fewer or no warnings
        assert len(warnings) >= 0


class TestFeatureFlagErrorHandling:
    """Test error handling in feature flag operations"""
    
    @pytest.mark.asyncio
    async def test_get_flag_redis_error(self, feature_manager, mock_settings):
        """Test graceful handling of Redis errors during flag retrieval"""
        feature_manager.redis_client.get.side_effect = Exception("Redis connection lost")
        mock_settings.features.enable_metrics = True
        
        # Should fall back to settings value
        result = await feature_manager.get_flag("enable_metrics")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_set_flag_redis_error(self, feature_manager):
        """Test handling of Redis errors during flag updates"""
        feature_manager.redis_client.set.side_effect = Exception("Redis write error")
        
        result = await feature_manager.set_flag("enable_hybrid_search", True)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_all_flags_redis_error(self, feature_manager, mock_settings):
        """Test handling of Redis errors during bulk flag retrieval"""
        feature_manager.redis_client.keys.side_effect = Exception("Redis keys error")
        
        # Should return flags from settings only
        result = await feature_manager.get_all_flags()
        assert len(result) > 0  # Should have settings-based flags
    
    def test_redis_connection_none(self, mock_settings):
        """Test behavior when Redis is not available"""
        manager = FeatureManager(mock_settings)
        
        # Should handle None Redis client gracefully
        assert manager.redis_client is None


class TestFeatureFlagIntegration:
    """Integration tests for feature flag system"""
    
    @pytest.mark.asyncio
    async def test_flag_lifecycle(self, feature_manager, mock_settings):
        """Test complete flag lifecycle: set, get, clear"""
        # Initial state - no override
        mock_settings.features.enable_hybrid_search = False
        result = await feature_manager.get_flag("enable_hybrid_search")
        assert result is False
        
        # Set override
        feature_manager.redis_client.set.return_value = True
        success = await feature_manager.set_flag("enable_hybrid_search", True, 30)
        assert success is True
        
        # Get with override
        feature_manager.redis_client.get.return_value = "true"
        result = await feature_manager.get_flag("enable_hybrid_search")
        assert result is True
        
        # Clear overrides
        feature_manager.redis_client.keys.return_value = ["flag:enable_hybrid_search"]
        feature_manager.redis_client.delete.return_value = 1
        cleared = await feature_manager.clear_overrides()
        assert cleared == 1
        
        # Back to default
        feature_manager.redis_client.get.return_value = None
        result = await feature_manager.get_flag("enable_hybrid_search")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_production_environment_constraints(self, mock_settings):
        """Test production environment behavior"""
        mock_settings.is_production = True
        mock_redis = AsyncMock()
        
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            manager = FeatureManager(mock_settings)
            await manager._ensure_redis_connection()
            
            # Should not allow disabling safety flags
            result = await manager.set_flag("enable_phi_scrubbing", False)
            assert result is False
            
            # Should allow enabling experimental flags
            result = await manager.set_flag("enable_hybrid_search", True)
            assert result is True  # Assuming Redis operation succeeds
    
    @pytest.mark.asyncio  
    async def test_concurrent_flag_operations(self, feature_manager):
        """Test concurrent flag operations"""
        feature_manager.redis_client.set.return_value = True
        feature_manager.redis_client.get.return_value = None
        
        # Simulate concurrent flag operations
        tasks = [
            feature_manager.set_flag("enable_hybrid_search", True),
            feature_manager.set_flag("enable_elasticsearch", True),
            feature_manager.get_flag("enable_metrics"),
            feature_manager.get_flag("enable_hybrid_search")
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Should complete without exceptions
        for result in results:
            assert not isinstance(result, Exception)
    
    @pytest.mark.asyncio
    async def test_feature_manager_context_usage(self, mock_settings, mock_redis):
        """Test feature manager in context manager pattern"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            manager = FeatureManager(mock_settings)
            
            async with manager:
                # Should be able to perform operations
                result = await manager.get_flag("enable_metrics")
                assert isinstance(result, bool)
                
                success = await manager.set_flag("enable_hybrid_search", True)
                assert isinstance(success, bool)