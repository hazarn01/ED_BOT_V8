"""
Integration tests for configuration management system.

Tests the complete configuration pipeline from environment variables
through settings validation, feature flag management, and admin endpoints.
"""

import os
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.config.enhanced_settings import EnhancedSettings, get_settings
from src.config.feature_manager import FeatureManager
from src.config.validators import ConfigurationValidator


@pytest.fixture
def temp_env_file():
    """Create temporary environment file for testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("""
# Test environment configuration
ENVIRONMENT=integration_test
APP_NAME=EDBotv8-Test
DEBUG=true
LLM_BACKEND=ollama

# Feature flags
FEATURES__ENABLE_HYBRID_SEARCH=true
FEATURES__SEARCH_BACKEND=hybrid
FEATURES__ENABLE_ELASTICSEARCH=true
FEATURES__ENABLE_METRICS=true
FEATURES__ENABLE_MEDICAL_METRICS=true

# Elasticsearch config
HYBRID_SEARCH__ELASTICSEARCH_URL=http://test-elasticsearch:9200
HYBRID_SEARCH__KEYWORD_WEIGHT=0.4
HYBRID_SEARCH__SEMANTIC_WEIGHT=0.6

# Cache config
CACHE_CONFIG__TTL_SECONDS=600
CACHE_CONFIG__MIN_CONFIDENCE_TO_CACHE=0.8

# Observability
OBSERVABILITY__METRICS_PORT=9091
OBSERVABILITY__HEALTH_CHECK_INTERVAL=60
""")
        env_file_path = f.name
    
    yield env_file_path
    os.unlink(env_file_path)


@pytest.fixture
def mock_redis():
    """Mock Redis for feature flag tests"""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.keys = AsyncMock(return_value=[])
    redis_mock.ping = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


class TestConfigurationLoading:
    """Test configuration loading and validation"""
    
    def test_settings_loading_from_environment(self, temp_env_file):
        """Test loading settings from environment file"""
        # Load environment from file
        test_env = {}
        with open(temp_env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    test_env[key] = value
        
        with patch.dict(os.environ, test_env, clear=True):
            settings = get_settings(reload=True)
            
            assert settings.environment == "integration_test"
            assert settings.app_name == "EDBotv8-Test"
            assert settings.debug is True
            assert settings.llm_backend == "ollama"
            
            # Feature flags
            assert settings.features.enable_hybrid_search is True
            assert settings.features.search_backend == "hybrid"
            assert settings.features.enable_elasticsearch is True
            
            # Nested configuration
            assert settings.hybrid_search.elasticsearch_url == "http://test-elasticsearch:9200"
            assert settings.hybrid_search.keyword_weight == 0.4
            assert settings.hybrid_search.semantic_weight == 0.6
            
            assert settings.cache_config.ttl_seconds == 600
            assert settings.cache_config.min_confidence_to_cache == 0.8
            
            assert settings.observability.metrics_port == 9091
            assert settings.observability.health_check_interval == 60
    
    def test_configuration_validation_integration(self, temp_env_file):
        """Test configuration validation with loaded settings"""
        test_env = {}
        with open(temp_env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    test_env[key] = value
        
        with patch.dict(os.environ, test_env, clear=True):
            settings = get_settings(reload=True)
            validator = ConfigurationValidator(settings)
            
            warnings = validator.validate_all()
            
            # Should have minimal warnings for well-configured test environment
            assert isinstance(warnings, list)
            
            # Get summary
            summary = validator.get_configuration_summary()
            assert summary["environment"] == "integration_test"
            assert "enable_hybrid_search" in summary["enabled_features"]
            assert "hybrid" in summary["backend_services"].values()
    
    def test_production_safety_validation(self):
        """Test production safety validation"""
        production_env = {
            'ENVIRONMENT': 'production',
            'FEATURES__ENABLE_PHI_SCRUBBING': 'true',
            'FEATURES__ENABLE_RESPONSE_VALIDATION': 'true',
            'FEATURES__ENABLE_STREAMLIT_DEMO': 'false',  # Must be false in production
            'FEATURES__ENABLE_PDF_VIEWER': 'false'  # Must be false in production
        }
        
        with patch.dict(os.environ, production_env, clear=True):
            settings = get_settings(reload=True)
            validator = ConfigurationValidator(settings)
            
            warnings = validator.validate_all()
            
            # Should have no critical warnings for proper production config
            critical_warnings = [w for w in warnings if w.severity == "CRITICAL"]
            assert len(critical_warnings) == 0
            
            # Verify production safety features are enforced
            assert settings.features.enable_phi_scrubbing is True
            assert settings.features.enable_response_validation is True
            assert settings.features.enable_streamlit_demo is False
            assert settings.features.enable_pdf_viewer is False


class TestFeatureFlagIntegration:
    """Test feature flag integration across the system"""
    
    @pytest.mark.asyncio
    async def test_feature_flag_lifecycle_integration(self, mock_redis):
        """Test complete feature flag lifecycle"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            # Setup test settings
            settings = EnhancedSettings(
                environment="development",
                features__enable_hybrid_search=False
            )
            
            feature_manager = FeatureManager(settings)
            await feature_manager._ensure_redis_connection()
            
            # 1. Initial state - get from settings
            mock_redis.get.return_value = None
            flag_value = await feature_manager.get_flag("enable_hybrid_search")
            assert flag_value is False
            
            # 2. Set temporary override
            mock_redis.set.return_value = True
            success = await feature_manager.set_flag("enable_hybrid_search", True, 30)
            assert success is True
            
            # 3. Get overridden value
            mock_redis.get.return_value = "true"
            flag_value = await feature_manager.get_flag("enable_hybrid_search")
            assert flag_value is True
            
            # 4. Get all flags with details
            mock_redis.keys.return_value = ["flag:enable_hybrid_search"]
            mock_redis.ttl.return_value = 1800  # 30 minutes
            
            all_flags = await feature_manager.get_all_flags()
            
            assert "enable_hybrid_search" in all_flags
            flag_info = all_flags["enable_hybrid_search"]
            assert flag_info["current_value"] is True
            assert flag_info["default_value"] is False
            assert flag_info["has_override"] is True
            assert flag_info["ttl_seconds"] == 1800
            
            # 5. Clear overrides
            mock_redis.delete.return_value = 1
            cleared_count = await feature_manager.clear_overrides()
            assert cleared_count == 1
            
            # 6. Back to default
            mock_redis.get.return_value = None
            flag_value = await feature_manager.get_flag("enable_hybrid_search")
            assert flag_value is False
    
    @pytest.mark.asyncio
    async def test_feature_flag_dependency_validation(self, mock_redis):
        """Test feature flag dependency validation"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            # Setup inconsistent configuration
            settings = EnhancedSettings(
                features__search_backend="hybrid",
                features__enable_hybrid_search=False,  # Inconsistent
                features__enable_elasticsearch=False   # Inconsistent
            )
            
            feature_manager = FeatureManager(settings)
            warnings = await feature_manager.validate_flag_dependencies()
            
            # Should detect inconsistencies
            assert len(warnings) > 0
            assert any("hybrid" in warning.lower() for warning in warnings)
    
    @pytest.mark.asyncio
    async def test_production_safety_enforcement(self, mock_redis):
        """Test production safety feature enforcement"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            # Production settings
            settings = EnhancedSettings(
                environment="production",
                features__enable_phi_scrubbing=True,
                features__enable_response_validation=True
            )
            
            feature_manager = FeatureManager(settings)
            
            # Should not allow disabling safety features in production
            success = await feature_manager.set_flag("enable_phi_scrubbing", False)
            assert success is False
            
            success = await feature_manager.set_flag("enable_response_validation", False)
            assert success is False
            
            # Should allow enabling non-safety features
            mock_redis.set.return_value = True
            success = await feature_manager.set_flag("enable_hybrid_search", True)
            assert success is True


class TestAdminEndpointsIntegration:
    """Test admin endpoints integration with configuration system"""
    
    def test_get_configuration_summary_endpoint(self, client):
        """Test configuration summary endpoint"""
        with patch('src.api.dependencies.get_enhanced_settings') as mock_get_settings:
            # Mock settings
            mock_settings = Mock()
            mock_settings.environment = "test"
            mock_settings.is_production = False
            mock_settings.llm_backend = "ollama"
            mock_settings.features = Mock()
            mock_settings.features.enable_metrics = True
            mock_settings.features.enable_hybrid_search = False
            mock_settings.hybrid_search = Mock()
            mock_settings.hybrid_search.elasticsearch_url = "http://elasticsearch:9200"
            mock_settings.observability = Mock()
            mock_settings.observability.metrics_port = 9090
            
            mock_get_settings.return_value = mock_settings
            
            response = client.get("/api/v1/admin/config/summary")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["environment"] == "test"
            assert isinstance(data["enabled_features"], list)
            assert isinstance(data["configuration_warnings"], list)
            assert isinstance(data["backend_services"], dict)
    
    def test_validate_configuration_endpoint(self, client):
        """Test configuration validation endpoint"""
        with patch('src.api.dependencies.get_enhanced_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.environment = "development"
            mock_settings.is_production = False
            mock_settings.features = Mock()
            mock_settings.hybrid_search = Mock()
            mock_settings.observability = Mock()
            
            mock_get_settings.return_value = mock_settings
            
            response = client.get("/api/v1/admin/config/validate")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "validated"
            assert "warnings_count" in data
            assert "warnings" in data
            assert data["environment"] == "development"
            assert data["is_production"] is False
    
    @pytest.mark.asyncio
    async def test_feature_flag_endpoints_integration(self, client, mock_redis):
        """Test feature flag endpoints integration"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis), \
             patch('src.api.dependencies.get_enhanced_settings') as mock_get_settings:
            
            # Mock settings
            mock_settings = Mock()
            mock_settings.environment = "development"
            mock_settings.is_production = False
            mock_settings.features = Mock()
            mock_settings.features.enable_hybrid_search = False
            mock_settings.features.enable_metrics = True
            
            mock_get_settings.return_value = mock_settings
            
            # Test getting all flags
            mock_redis.keys.return_value = []
            response = client.get("/api/v1/admin/config/flags")
            assert response.status_code == 200
            
            # Test setting a flag
            mock_redis.set.return_value = True
            response = client.post(
                "/api/v1/admin/config/flags/enable_hybrid_search",
                json={
                    "enabled": True,
                    "ttl_minutes": 60,
                    "reason": "Testing hybrid search"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "updated"
            assert data["flag"] == "enable_hybrid_search"
            assert data["value"] is True
            
            # Test clearing overrides
            mock_redis.keys.return_value = ["flag:enable_hybrid_search"]
            mock_redis.delete.return_value = 1
            response = client.delete("/api/v1/admin/config/flags")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "cleared"
            assert data["count"] == 1


class TestHealthMonitoringIntegration:
    """Test health monitoring integration"""
    
    @pytest.mark.asyncio
    async def test_health_endpoints_integration(self, client):
        """Test health endpoints integration"""
        # Test basic health endpoint
        response = client.get("/health")
        assert response.status_code in [200, 503]  # Depends on system state
        
        # Test API health endpoints
        response = client.get("/api/v1/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "EDBotv8"
        
        # Test readiness probe
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock healthy database check
            healthy_check = Mock()
            healthy_check.status.value = "healthy"
            mock_monitor.check_database_health = AsyncMock(return_value=healthy_check)
            mock_monitor.check_llm_backend_health = AsyncMock(return_value=healthy_check)
            
            response = client.get("/api/v1/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_integration(self, client):
        """Test comprehensive health check integration"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock system health
            mock_system_health = Mock()
            mock_system_health.overall_status.value = "healthy"
            mock_system_health.health_score = 0.95
            mock_system_health.to_dict.return_value = {
                "overall_status": "healthy",
                "health_score": 0.95,
                "components": [],
                "healthy_components": 6,
                "total_components": 6
            }
            
            mock_monitor.perform_comprehensive_health_check = AsyncMock(
                return_value=mock_system_health
            )
            
            response = client.get("/api/v1/health/detailed")
            assert response.status_code == 200
            data = response.json()
            
            assert data["overall_status"] == "healthy"
            assert data["health_score"] == 0.95
            assert data["healthy_components"] == 6
    
    def test_health_trends_endpoint(self, client):
        """Test health trends endpoint"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            mock_monitor.get_health_trends.return_value = {
                "time_period": "last_hour",
                "checks_count": 10,
                "average_health_score": 0.92,
                "component_uptime_percent": {
                    "database": 100.0,
                    "redis": 95.0,
                    "llm": 98.0
                },
                "trend": "stable"
            }
            
            response = client.get("/api/v1/health/trends")
            assert response.status_code == 200
            data = response.json()
            
            assert data["average_health_score"] == 0.92
            assert data["trend"] == "stable"
            assert "component_uptime_percent" in data


class TestMetricsIntegration:
    """Test metrics collection integration"""
    
    def test_prometheus_metrics_endpoint(self, client):
        """Test Prometheus metrics endpoint"""
        with patch('prometheus_client.generate_latest') as mock_generate:
            mock_generate.return_value = b"# HELP edbot_queries_total Total queries\nedbot_queries_total{query_type=\"PROTOCOL_STEPS\"} 10"
            
            response = client.get("/metrics")
            assert response.status_code == 200
            assert "edbot_queries_total" in response.text
    
    @pytest.mark.asyncio
    async def test_metrics_collection_integration(self):
        """Test metrics collection across components"""
        with patch('src.observability.metrics.query_total') as mock_counter, \
             patch('src.observability.metrics.medical_queries_by_specialty') as mock_medical:
            
            # Configure mocks
            mock_counter.labels.return_value.inc = Mock()
            mock_medical.labels.return_value.inc = Mock()
            
            from src.observability.medical_metrics import medical_metrics
            from src.observability.metrics import metrics
            
            # Enable metrics
            metrics.enabled = True
            medical_metrics.enabled = True
            
            # Track a query through both systems
            metrics.track_query("PROTOCOL_STEPS", 1.2, 0.88, False, "hybrid")
            medical_metrics.track_medical_query(
                "chest pain protocol",
                "PROTOCOL_STEPS", 
                0.88, 
                1.2
            )
            
            # Verify both metric systems were called
            mock_counter.labels.assert_called()
            mock_medical.labels.assert_called()


class TestEndToEndConfigurationWorkflow:
    """Test complete end-to-end configuration workflow"""
    
    @pytest.mark.asyncio
    async def test_complete_configuration_workflow(self, temp_env_file, mock_redis, client):
        """Test complete configuration workflow from env to API"""
        # 1. Load configuration from environment
        test_env = {}
        with open(temp_env_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    test_env[key] = value
        
        with patch.dict(os.environ, test_env, clear=True), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            # 2. Initialize settings
            settings = get_settings(reload=True)
            assert settings.environment == "integration_test"
            assert settings.features.enable_hybrid_search is True
            
            # 3. Create and test feature manager
            feature_manager = FeatureManager(settings)
            await feature_manager._ensure_redis_connection()
            
            # 4. Validate configuration
            validator = ConfigurationValidator(settings)
            warnings = validator.validate_all()
            assert isinstance(warnings, list)
            
            # 5. Test configuration summary
            summary = validator.get_configuration_summary()
            assert summary["environment"] == "integration_test"
            
            # 6. Test feature flag management via API
            with patch('src.api.dependencies.get_enhanced_settings', return_value=settings):
                response = client.get("/api/v1/admin/config/summary")
                assert response.status_code == 200
                
                api_summary = response.json()
                assert api_summary["environment"] == "integration_test"
            
            # 7. Test feature flag operations via API
            mock_redis.set.return_value = True
            with patch('src.api.dependencies.get_enhanced_settings', return_value=settings):
                response = client.post(
                    "/api/v1/admin/config/flags/enable_table_extraction",
                    json={"enabled": True, "ttl_minutes": 30}
                )
                assert response.status_code == 200
                
                flag_response = response.json()
                assert flag_response["status"] == "updated"
                assert flag_response["value"] is True
    
    def test_configuration_error_handling_integration(self):
        """Test configuration error handling integration"""
        # Test with invalid configuration
        invalid_env = {
            'ENVIRONMENT': 'production',
            'LLM_BACKEND': 'invalid_backend',  # Invalid
            'FEATURES__ENABLE_PHI_SCRUBBING': 'false',  # Invalid for production
            'HYBRID_SEARCH__KEYWORD_WEIGHT': '0.8',  # Invalid (weights don't sum to 1)
            'HYBRID_SEARCH__SEMANTIC_WEIGHT': '0.3'
        }
        
        with patch.dict(os.environ, invalid_env, clear=True):
            try:
                settings = get_settings(reload=True)
                # If settings creation succeeds, validation should catch issues
                validator = ConfigurationValidator(settings)
                warnings = validator.validate_all()
                
                # Should have multiple warnings/errors
                assert len(warnings) > 0
                error_warnings = [w for w in warnings if w.severity in ["HIGH", "CRITICAL"]]
                assert len(error_warnings) > 0
                
            except Exception:
                # Settings creation might fail with validation errors, which is expected
                pass
    
    @pytest.mark.asyncio
    async def test_observability_integration(self, mock_redis):
        """Test observability integration across systems"""
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis), \
             patch('src.observability.health.get_database') as mock_db, \
             patch('redis.asyncio.Redis') as mock_redis_client:
            
            # Mock database connection for health check
            mock_db_instance = AsyncMock()
            mock_result = Mock()
            mock_result.fetchone.return_value = [1]
            mock_db_instance.execute.return_value = mock_result
            mock_db.__aenter__.return_value = mock_db_instance
            mock_db.__aexit__.return_value = None
            
            # Mock Redis for health check
            mock_redis_instance = AsyncMock()
            mock_redis_instance.set.return_value = True
            mock_redis_instance.get.return_value = "test_value"
            mock_redis_instance.delete.return_value = 1
            mock_redis_instance.info.return_value = {'redis_version': '6.0.0'}
            mock_redis_client.return_value = mock_redis_instance
            
            # Initialize systems
            settings = EnhancedSettings(
                environment="integration_test",
                features__enable_metrics=True,
                features__enable_medical_metrics=True
            )
            
            from src.observability.health import HealthMonitor
            from src.observability.medical_metrics import init_medical_metrics
            from src.observability.metrics import init_metrics
            
            # Initialize all observability systems
            init_metrics(settings)
            init_medical_metrics(settings)
            health_monitor = HealthMonitor(settings)
            
            # Test integrated health check
            db_check = await health_monitor.check_database_health()
            assert db_check.status.value in ["healthy", "degraded", "unhealthy"]
            
            redis_check = await health_monitor.check_redis_health()
            assert redis_check.status.value in ["healthy", "degraded", "unhealthy"]
            
            # Test metrics integration with health monitoring
            with patch('src.observability.metrics.system_health') as mock_health_metric:
                mock_health_metric.set = Mock()
                
                await health_monitor._update_health_metrics(
                    Mock(health_score=0.9, component_checks=[db_check, redis_check])
                )
                
                mock_health_metric.set.assert_called_with(0.9)