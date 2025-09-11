"""
Performance tests for configuration management system.

Tests configuration loading, feature flag operations, and validation
performance to ensure minimal impact on system startup and runtime.
"""

import asyncio
import os
import statistics
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.config.enhanced_settings import EnhancedSettings, get_settings
from src.config.feature_manager import FeatureManager
from src.config.validators import ConfigurationValidator


@pytest.fixture
def performance_env_vars():
    """Environment variables for performance testing"""
    return {
        'ENVIRONMENT': 'performance_test',
        'APP_NAME': 'EDBotv8-Performance',
        'DEBUG': 'false',
        'LLM_BACKEND': 'ollama',
        
        # Feature flags
        'FEATURES__ENABLE_HYBRID_SEARCH': 'true',
        'FEATURES__SEARCH_BACKEND': 'hybrid',
        'FEATURES__ENABLE_ELASTICSEARCH': 'true',
        'FEATURES__ENABLE_METRICS': 'true',
        'FEATURES__ENABLE_MEDICAL_METRICS': 'true',
        'FEATURES__ENABLE_PHI_SCRUBBING': 'true',
        'FEATURES__ENABLE_RESPONSE_VALIDATION': 'true',
        
        # Nested configuration
        'HYBRID_SEARCH__ELASTICSEARCH_URL': 'http://elasticsearch:9200',
        'HYBRID_SEARCH__KEYWORD_WEIGHT': '0.3',
        'HYBRID_SEARCH__SEMANTIC_WEIGHT': '0.7',
        'CACHE_CONFIG__TTL_SECONDS': '300',
        'CACHE_CONFIG__MIN_CONFIDENCE_TO_CACHE': '0.8',
        'OBSERVABILITY__METRICS_PORT': '9090',
        'OBSERVABILITY__HEALTH_CHECK_INTERVAL': '30'
    }


@pytest.fixture
def mock_redis():
    """Mock Redis for feature flag performance testing"""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.keys = AsyncMock(return_value=[])
    redis_mock.ttl = AsyncMock(return_value=-1)
    redis_mock.ping = AsyncMock(return_value=True)
    return redis_mock


class TestSettingsLoadingPerformance:
    """Test settings loading and initialization performance"""
    
    def test_settings_initialization_performance(self, performance_env_vars):
        """Test settings initialization time"""
        with patch.dict(os.environ, performance_env_vars, clear=True):
            # Cold initialization
            start_time = time.perf_counter()
            settings = EnhancedSettings()
            cold_init_time = time.perf_counter() - start_time
            
            print(f"Cold settings initialization: {cold_init_time*1000:.2f}ms")
            
            # Warm initialization (should use validation caching)
            start_time = time.perf_counter()
            settings2 = EnhancedSettings()
            warm_init_time = time.perf_counter() - start_time
            
            print(f"Warm settings initialization: {warm_init_time*1000:.2f}ms")
            
            # Verify settings are valid
            assert settings.environment == "performance_test"
            assert settings.features.enable_hybrid_search is True
            assert settings2.environment == "performance_test"
            
            # Cold initialization should be reasonable (< 100ms)
            assert cold_init_time < 0.1, f"Settings initialization too slow: {cold_init_time*1000:.2f}ms"
            
            # Warm initialization should be fast (< 50ms)
            assert warm_init_time < 0.05, f"Warm settings initialization too slow: {warm_init_time*1000:.2f}ms"
    
    def test_settings_singleton_performance(self, performance_env_vars):
        """Test settings singleton access performance"""
        with patch.dict(os.environ, performance_env_vars, clear=True):
            # First access (initialization)
            start_time = time.perf_counter()
            settings1 = get_settings()
            first_access_time = time.perf_counter() - start_time
            
            # Subsequent accesses (should return cached instance)
            access_times = []
            for _ in range(1000):
                start_time = time.perf_counter()
                settings = get_settings()
                access_time = time.perf_counter() - start_time
                access_times.append(access_time)
                assert settings is settings1  # Same instance
            
            avg_access_time = statistics.mean(access_times)
            max_access_time = max(access_times)
            
            print(f"First settings access: {first_access_time*1000:.2f}ms")
            print(f"Average subsequent access: {avg_access_time*1000000:.1f}μs")
            print(f"Max subsequent access: {max_access_time*1000000:.1f}μs")
            
            # Subsequent accesses should be extremely fast (< 100μs average)
            assert avg_access_time < 0.0001, f"Settings access too slow: {avg_access_time*1000000:.1f}μs"
            assert max_access_time < 0.001, f"Max settings access too slow: {max_access_time*1000000:.1f}μs"
    
    def test_environment_variable_parsing_performance(self):
        """Test environment variable parsing performance"""
        # Create large environment with many variables
        large_env = {}
        for i in range(1000):
            large_env[f'TEST_VAR_{i}'] = f'test_value_{i}'
        
        # Add our actual config variables
        large_env.update({
            'ENVIRONMENT': 'performance_test',
            'FEATURES__ENABLE_HYBRID_SEARCH': 'true',
            'FEATURES__ENABLE_ELASTICSEARCH': 'true',
            'HYBRID_SEARCH__ELASTICSEARCH_URL': 'http://elasticsearch:9200',
            'CACHE_CONFIG__TTL_SECONDS': '300'
        })
        
        with patch.dict(os.environ, large_env, clear=True):
            start_time = time.perf_counter()
            settings = EnhancedSettings()
            parse_time = time.perf_counter() - start_time
            
            print(f"Environment parsing with 1000+ vars: {parse_time*1000:.2f}ms")
            
            # Should handle large environments efficiently (< 200ms)
            assert parse_time < 0.2, f"Environment parsing too slow: {parse_time*1000:.2f}ms"
            assert settings.environment == "performance_test"
    
    def test_nested_configuration_access_performance(self, performance_env_vars):
        """Test nested configuration access performance"""
        with patch.dict(os.environ, performance_env_vars, clear=True):
            settings = EnhancedSettings()
            
            # Test nested attribute access performance
            start_time = time.perf_counter()
            
            for _ in range(10000):
                # Access nested configuration attributes
                _ = settings.features.enable_hybrid_search
                _ = settings.hybrid_search.elasticsearch_url
                _ = settings.cache_config.ttl_seconds
                _ = settings.observability.metrics_port
            
            access_time = time.perf_counter() - start_time
            accesses_per_second = 40000 / access_time  # 4 accesses per iteration
            
            print(f"Nested config access: {accesses_per_second:.0f} accesses/second")
            
            # Should handle very high access rates (> 100,000 accesses/second)
            assert accesses_per_second > 100000, f"Nested access too slow: {accesses_per_second:.0f}/sec"


class TestFeatureFlagPerformance:
    """Test feature flag system performance"""
    
    @pytest.mark.asyncio
    async def test_feature_flag_get_performance(self, mock_redis):
        """Test feature flag retrieval performance"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            settings = EnhancedSettings(
                environment="performance_test",
                features__enable_hybrid_search=False,
                features__enable_elasticsearch=True
            )
            
            feature_manager = FeatureManager(settings)
            await feature_manager._ensure_redis_connection()
            
            # Mock Redis responses for cache miss (settings lookup)
            mock_redis.get.return_value = None
            
            # Test cold access (no cache)
            start_time = time.perf_counter()
            flag_value = await feature_manager.get_flag("enable_hybrid_search")
            cold_access_time = time.perf_counter() - start_time
            assert flag_value is False
            
            # Test warm access (with cache)
            warm_access_times = []
            for _ in range(1000):
                start_time = time.perf_counter()
                flag_value = await feature_manager.get_flag("enable_hybrid_search")
                access_time = time.perf_counter() - start_time
                warm_access_times.append(access_time)
                assert flag_value is False
            
            avg_warm_time = statistics.mean(warm_access_times)
            
            print(f"Cold flag access: {cold_access_time*1000:.2f}ms")
            print(f"Warm flag access (avg): {avg_warm_time*1000000:.1f}μs")
            
            # Cold access should be reasonable (< 10ms)
            assert cold_access_time < 0.01, f"Cold flag access too slow: {cold_access_time*1000:.2f}ms"
            
            # Warm access should be very fast (< 100μs with caching)
            assert avg_warm_time < 0.0001, f"Warm flag access too slow: {avg_warm_time*1000000:.1f}μs"
    
    @pytest.mark.asyncio
    async def test_feature_flag_set_performance(self, mock_redis):
        """Test feature flag setting performance"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            settings = EnhancedSettings(environment="development")
            feature_manager = FeatureManager(settings)
            await feature_manager._ensure_redis_connection()
            
            mock_redis.set.return_value = True
            
            # Test flag setting performance
            set_times = []
            for i in range(100):
                start_time = time.perf_counter()
                success = await feature_manager.set_flag("enable_hybrid_search", i % 2 == 0, 60)
                set_time = time.perf_counter() - start_time
                set_times.append(set_time)
                assert success is True
            
            avg_set_time = statistics.mean(set_times)
            max_set_time = max(set_times)
            
            print(f"Flag set time (avg): {avg_set_time*1000:.2f}ms")
            print(f"Flag set time (max): {max_set_time*1000:.2f}ms")
            
            # Flag setting should be fast (< 20ms average)
            assert avg_set_time < 0.02, f"Flag setting too slow: {avg_set_time*1000:.2f}ms"
            assert max_set_time < 0.05, f"Max flag setting too slow: {max_set_time*1000:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_concurrent_feature_flag_access(self, mock_redis):
        """Test concurrent feature flag access performance"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            settings = EnhancedSettings(
                environment="performance_test",
                features__enable_hybrid_search=True,
                features__enable_elasticsearch=False
            )
            
            feature_manager = FeatureManager(settings)
            await feature_manager._ensure_redis_connection()
            
            mock_redis.get.return_value = None  # Cache miss, use settings
            
            async def concurrent_flag_access(iterations=100):
                """Access flags concurrently"""
                tasks = []
                for i in range(iterations):
                    flag_name = ["enable_hybrid_search", "enable_elasticsearch", "enable_metrics"][i % 3]
                    task = feature_manager.get_flag(flag_name)
                    tasks.append(task)
                
                return await asyncio.gather(*tasks)
            
            start_time = time.perf_counter()
            results = await concurrent_flag_access(300)  # 300 concurrent accesses
            concurrent_time = time.perf_counter() - start_time
            
            accesses_per_second = 300 / concurrent_time
            
            print(f"Concurrent flag access: {accesses_per_second:.0f} accesses/second")
            print(f"Total time for 300 concurrent: {concurrent_time*1000:.2f}ms")
            
            # Should handle high concurrent access rates (> 5000/sec)
            assert accesses_per_second > 5000, f"Concurrent access too slow: {accesses_per_second:.0f}/sec"
            assert len(results) == 300
    
    @pytest.mark.asyncio
    async def test_feature_flag_cache_performance(self, mock_redis):
        """Test feature flag caching effectiveness"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            settings = EnhancedSettings(features__enable_hybrid_search=True)
            feature_manager = FeatureManager(settings)
            feature_manager.cache_ttl = 300  # 5 minutes
            await feature_manager._ensure_redis_connection()
            
            mock_redis.get.return_value = None
            
            # First access (cache miss)
            start_time = time.perf_counter()
            await feature_manager.get_flag("enable_hybrid_search")
            cache_miss_time = time.perf_counter() - start_time
            
            # Subsequent accesses (cache hits)
            cache_hit_times = []
            for _ in range(100):
                start_time = time.perf_counter()
                await feature_manager.get_flag("enable_hybrid_search")
                hit_time = time.perf_counter() - start_time
                cache_hit_times.append(hit_time)
            
            avg_hit_time = statistics.mean(cache_hit_times)
            
            print(f"Cache miss time: {cache_miss_time*1000000:.1f}μs")
            print(f"Cache hit time (avg): {avg_hit_time*1000000:.1f}μs")
            
            # Cache hits should be much faster than misses
            speedup_ratio = cache_miss_time / avg_hit_time
            print(f"Cache speedup: {speedup_ratio:.1f}x")
            
            assert speedup_ratio > 5, f"Cache not effective enough: {speedup_ratio:.1f}x speedup"
            assert avg_hit_time < 0.00005, f"Cache hits too slow: {avg_hit_time*1000000:.1f}μs"
    
    @pytest.mark.asyncio
    async def test_bulk_flag_operations_performance(self, mock_redis):
        """Test bulk flag operations performance"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            settings = EnhancedSettings(environment="performance_test")
            feature_manager = FeatureManager(settings)
            await feature_manager._ensure_redis_connection()
            
            # Mock bulk Redis responses
            mock_redis.keys.return_value = [f"flag:test_flag_{i}" for i in range(50)]
            mock_redis.get.side_effect = [None] * 50  # All cache misses
            mock_redis.ttl.side_effect = [-1] * 50   # No TTL
            
            start_time = time.perf_counter()
            all_flags = await feature_manager.get_all_flags()
            bulk_get_time = time.perf_counter() - start_time
            
            print(f"Bulk get all flags: {bulk_get_time*1000:.2f}ms for {len(all_flags)} flags")
            
            # Clear overrides performance
            mock_redis.delete.return_value = 50
            start_time = time.perf_counter()
            cleared = await feature_manager.clear_overrides()
            clear_time = time.perf_counter() - start_time
            
            print(f"Clear overrides: {clear_time*1000:.2f}ms for {cleared} flags")
            
            # Bulk operations should be efficient
            assert bulk_get_time < 0.1, f"Bulk get too slow: {bulk_get_time*1000:.2f}ms"
            assert clear_time < 0.05, f"Clear overrides too slow: {clear_time*1000:.2f}ms"


class TestConfigurationValidationPerformance:
    """Test configuration validation performance"""
    
    def test_validation_performance(self, performance_env_vars):
        """Test configuration validation speed"""
        with patch.dict(os.environ, performance_env_vars, clear=True):
            settings = EnhancedSettings()
            
            # Single validation
            start_time = time.perf_counter()
            validator = ConfigurationValidator(settings)
            warnings = validator.validate_all()
            single_validation_time = time.perf_counter() - start_time
            
            print(f"Single validation: {single_validation_time*1000:.2f}ms")
            print(f"Warnings found: {len(warnings)}")
            
            # Multiple validations (test caching/optimization)
            validation_times = []
            for _ in range(50):
                start_time = time.perf_counter()
                validator = ConfigurationValidator(settings)
                warnings = validator.validate_all()
                validation_time = time.perf_counter() - start_time
                validation_times.append(validation_time)
            
            avg_validation_time = statistics.mean(validation_times)
            
            print(f"Average validation: {avg_validation_time*1000:.2f}ms")
            
            # Validation should be fast (< 50ms)
            assert single_validation_time < 0.05, f"Validation too slow: {single_validation_time*1000:.2f}ms"
            assert avg_validation_time < 0.03, f"Average validation too slow: {avg_validation_time*1000:.2f}ms"
    
    def test_validation_scalability(self):
        """Test validation performance with complex configurations"""
        # Create complex configuration
        complex_env = {}
        
        # Add many feature flags
        for i in range(100):
            complex_env[f'FEATURES__TEST_FLAG_{i}'] = 'true' if i % 2 == 0 else 'false'
        
        # Add nested configurations
        for i in range(50):
            complex_env[f'COMPLEX_CONFIG__{i}__VALUE'] = f'test_value_{i}'
            complex_env[f'COMPLEX_CONFIG__{i}__ENABLED'] = 'true'
        
        # Add core configuration
        complex_env.update({
            'ENVIRONMENT': 'performance_test',
            'FEATURES__ENABLE_HYBRID_SEARCH': 'true',
            'FEATURES__SEARCH_BACKEND': 'hybrid'
        })
        
        with patch.dict(os.environ, complex_env, clear=True):
            start_time = time.perf_counter()
            
            try:
                settings = EnhancedSettings()
                validator = ConfigurationValidator(settings)
                validator.validate_all()
                
                validation_time = time.perf_counter() - start_time
                
                print(f"Complex config validation: {validation_time*1000:.2f}ms")
                print(f"Environment variables: {len(complex_env)}")
                
                # Should handle complex configurations reasonably (< 200ms)
                assert validation_time < 0.2, f"Complex validation too slow: {validation_time*1000:.2f}ms"
                
            except Exception:
                # Some complex configs may be invalid, which is expected
                validation_time = time.perf_counter() - start_time
                print(f"Complex config validation (with errors): {validation_time*1000:.2f}ms")
                assert validation_time < 0.5, f"Error handling too slow: {validation_time*1000:.2f}ms"
    
    def test_configuration_summary_performance(self, performance_env_vars):
        """Test configuration summary generation performance"""
        with patch.dict(os.environ, performance_env_vars, clear=True):
            settings = EnhancedSettings()
            validator = ConfigurationValidator(settings)
            
            # Test summary generation
            summary_times = []
            for _ in range(20):
                start_time = time.perf_counter()
                summary = validator.get_configuration_summary()
                summary_time = time.perf_counter() - start_time
                summary_times.append(summary_time)
                
                assert isinstance(summary, dict)
                assert "environment" in summary
                assert "enabled_features" in summary
            
            avg_summary_time = statistics.mean(summary_times)
            
            print(f"Configuration summary: {avg_summary_time*1000:.2f}ms average")
            
            # Summary generation should be fast (< 20ms)
            assert avg_summary_time < 0.02, f"Summary generation too slow: {avg_summary_time*1000:.2f}ms"


class TestConfigurationMemoryUsage:
    """Test configuration system memory efficiency"""
    
    def test_settings_memory_usage(self, performance_env_vars):
        """Test settings memory consumption"""
        import os

        import psutil
        
        with patch.dict(os.environ, performance_env_vars, clear=True):
            process = psutil.Process(os.getpid())
            
            # Baseline memory
            baseline_memory = process.memory_info().rss
            
            # Create many settings instances
            settings_instances = []
            for _ in range(100):
                settings = EnhancedSettings()
                settings_instances.append(settings)
            
            # Memory after creating settings
            settings_memory = process.memory_info().rss
            memory_per_instance = (settings_memory - baseline_memory) / 100
            
            print(f"Memory per settings instance: {memory_per_instance / 1024:.1f} KB")
            
            # Each settings instance should use reasonable memory (< 100KB)
            assert memory_per_instance < 100 * 1024, f"Settings memory usage too high: {memory_per_instance/1024:.1f}KB"
            
            # Test singleton memory efficiency
            baseline_memory = process.memory_info().rss
            
            # Access singleton many times
            for _ in range(1000):
                settings = get_settings()
            
            singleton_memory = process.memory_info().rss
            singleton_overhead = singleton_memory - baseline_memory
            
            print(f"Singleton access overhead: {singleton_overhead / 1024:.1f} KB for 1000 accesses")
            
            # Singleton should have minimal memory overhead
            assert singleton_overhead < 10 * 1024, f"Singleton overhead too high: {singleton_overhead/1024:.1f}KB"
    
    @pytest.mark.asyncio
    async def test_feature_manager_memory_usage(self, mock_redis):
        """Test feature manager memory efficiency"""
        import os

        import psutil
        
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            process = psutil.Process(os.getpid())
            baseline_memory = process.memory_info().rss
            
            # Create many feature managers
            managers = []
            for i in range(50):
                settings = EnhancedSettings(environment="test")
                manager = FeatureManager(settings)
                await manager._ensure_redis_connection()
                managers.append(manager)
            
            manager_memory = process.memory_info().rss
            memory_per_manager = (manager_memory - baseline_memory) / 50
            
            print(f"Memory per feature manager: {memory_per_manager / 1024:.1f} KB")
            
            # Each manager should use reasonable memory (< 50KB)
            assert memory_per_manager < 50 * 1024, f"Feature manager memory too high: {memory_per_manager/1024:.1f}KB"
            
            # Test cache memory usage
            baseline_memory = process.memory_info().rss
            
            # Fill cache with many flags
            for manager in managers[:5]:  # Use subset to avoid overwhelming
                for i in range(20):
                    await manager.get_flag(f"test_flag_{i}")
            
            cache_memory = process.memory_info().rss
            cache_overhead = cache_memory - baseline_memory
            
            print(f"Cache memory overhead: {cache_overhead / 1024:.1f} KB for 100 cached flags")
            
            # Cache should be memory efficient
            assert cache_overhead < 100 * 1024, f"Cache memory overhead too high: {cache_overhead/1024:.1f}KB"


class TestStartupPerformance:
    """Test system startup performance with all components"""
    
    def test_complete_system_initialization(self, performance_env_vars):
        """Test complete system initialization time"""
        with patch.dict(os.environ, performance_env_vars, clear=True):
            
            def initialize_complete_system():
                """Initialize all configuration components"""
                # Settings initialization
                settings = get_settings(reload=True)
                
                # Validation
                validator = ConfigurationValidator(settings)
                warnings = validator.validate_all()
                
                # Summary generation
                summary = validator.get_configuration_summary()
                
                return settings, warnings, summary
            
            # Cold startup
            start_time = time.perf_counter()
            settings, warnings, summary = initialize_complete_system()
            cold_startup_time = time.perf_counter() - start_time
            
            # Warm startup (with caching)
            start_time = time.perf_counter()
            settings2, warnings2, summary2 = initialize_complete_system()
            warm_startup_time = time.perf_counter() - start_time
            
            print(f"Cold system startup: {cold_startup_time*1000:.2f}ms")
            print(f"Warm system startup: {warm_startup_time*1000:.2f}ms")
            
            # Verify initialization worked
            assert settings.environment == "performance_test"
            assert isinstance(warnings, list)
            assert isinstance(summary, dict)
            
            # Startup times should be reasonable
            assert cold_startup_time < 0.5, f"Cold startup too slow: {cold_startup_time*1000:.2f}ms"
            assert warm_startup_time < 0.1, f"Warm startup too slow: {warm_startup_time*1000:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_concurrent_system_initialization(self, performance_env_vars, mock_redis):
        """Test concurrent system initialization performance"""
        with patch.dict(os.environ, performance_env_vars, clear=True), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            async def initialize_system_component():
                """Initialize a complete system component"""
                settings = get_settings(reload=False)  # Use cached
                feature_manager = FeatureManager(settings)
                await feature_manager._ensure_redis_connection()
                
                # Access some flags
                flags = await asyncio.gather(
                    feature_manager.get_flag("enable_hybrid_search"),
                    feature_manager.get_flag("enable_metrics"),
                    feature_manager.get_flag("enable_medical_metrics")
                )
                
                return len(flags)
            
            start_time = time.perf_counter()
            
            # Initialize 10 concurrent "system components"
            tasks = [initialize_system_component() for _ in range(10)]
            results = await asyncio.gather(*tasks)
            
            concurrent_init_time = time.perf_counter() - start_time
            
            print(f"10 concurrent system initializations: {concurrent_init_time*1000:.2f}ms")
            
            # Concurrent initialization should be efficient
            assert concurrent_init_time < 0.2, f"Concurrent init too slow: {concurrent_init_time*1000:.2f}ms"
            assert all(result == 3 for result in results)  # All got 3 flags
    
    def test_configuration_hot_reload_performance(self, performance_env_vars):
        """Test configuration hot reload performance"""
        with patch.dict(os.environ, performance_env_vars, clear=True):
            # Initial load
            get_settings()
            
            # Modify environment
            modified_env = performance_env_vars.copy()
            modified_env['FEATURES__ENABLE_HYBRID_SEARCH'] = 'false'
            
            with patch.dict(os.environ, modified_env, clear=True):
                # Hot reload
                reload_times = []
                for _ in range(10):
                    start_time = time.perf_counter()
                    settings2 = get_settings(reload=True)
                    reload_time = time.perf_counter() - start_time
                    reload_times.append(reload_time)
                    
                    # Verify reload worked
                    assert settings2.features.enable_hybrid_search is False
                
                avg_reload_time = statistics.mean(reload_times)
                
                print(f"Hot reload time (avg): {avg_reload_time*1000:.2f}ms")
                
                # Hot reload should be fast (< 100ms)
                assert avg_reload_time < 0.1, f"Hot reload too slow: {avg_reload_time*1000:.2f}ms"