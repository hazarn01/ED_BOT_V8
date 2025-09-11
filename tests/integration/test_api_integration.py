"""
Integration tests for API endpoints with all new components.

Tests the complete API integration including configuration management,
health monitoring, metrics collection, and admin endpoints working together.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.config.enhanced_settings import EnhancedSettings
from src.observability.health import (
    ComponentType,
    HealthCheck,
    HealthStatus,
    SystemHealth,
)


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def mock_settings():
    """Mock enhanced settings for API testing"""
    settings = Mock(spec=EnhancedSettings)
    settings.environment = "integration_test"
    settings.is_production = False
    settings.app_name = "EDBotv8"
    settings.llm_backend = "ollama"
    
    # Mock feature flags
    settings.features = Mock()
    settings.features.enable_hybrid_search = False
    settings.features.enable_elasticsearch = False
    settings.features.enable_source_highlighting = True
    settings.features.enable_phi_scrubbing = True
    settings.features.enable_response_validation = True
    settings.features.enable_metrics = True
    settings.features.enable_medical_metrics = True
    settings.features.enable_streamlit_demo = False
    settings.features.search_backend = "pgvector"
    
    # Mock nested configs
    settings.hybrid_search = Mock()
    settings.hybrid_search.elasticsearch_url = "http://elasticsearch:9200"
    settings.hybrid_search.keyword_weight = 0.3
    settings.hybrid_search.semantic_weight = 0.7
    
    settings.observability = Mock()
    settings.observability.metrics_port = 9090
    settings.observability.health_check_interval = 30
    
    return settings


@pytest.fixture
def mock_redis():
    """Mock Redis for feature flag operations"""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.keys = AsyncMock(return_value=[])
    redis_mock.ttl = AsyncMock(return_value=-1)
    redis_mock.ping = AsyncMock(return_value=True)
    return redis_mock


class TestBasicAPIEndpoints:
    """Test basic API endpoints with new components"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code in [200, 404]  # Depends on static files
    
    def test_health_endpoint_basic(self, client):
        """Test basic health endpoint"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock healthy database check
            mock_db_check = Mock()
            mock_db_check.status.value = "healthy"
            mock_monitor.check_database_health = AsyncMock(return_value=mock_db_check)
            
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "ed-bot-v8"
            assert data["status"] in ["healthy", "unhealthy", "unknown"]
    
    def test_metrics_endpoint_basic(self, client):
        """Test basic metrics endpoint"""
        with patch('prometheus_client.generate_latest') as mock_generate:
            mock_generate.return_value = b"edbot_queries_total 0"
            
            response = client.get("/metrics")
            assert response.status_code == 200
            assert "edbot_queries_total" in response.text


class TestHealthAPIEndpoints:
    """Test health monitoring API endpoints"""
    
    def test_health_ready_endpoint(self, client):
        """Test readiness probe endpoint"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock healthy critical components
            healthy_check = HealthCheck(
                ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "OK"
            )
            mock_monitor.check_database_health = AsyncMock(return_value=healthy_check)
            mock_monitor.check_llm_backend_health = AsyncMock(return_value=healthy_check)
            
            response = client.get("/api/v1/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert "checks" in data
    
    def test_health_ready_endpoint_not_ready(self, client):
        """Test readiness probe when not ready"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock unhealthy database
            unhealthy_check = HealthCheck(
                ComponentType.DATABASE, HealthStatus.UNHEALTHY, 0.0, "Database down"
            )
            healthy_check = HealthCheck(
                ComponentType.LLM_BACKEND, HealthStatus.HEALTHY, 200.0, "LLM OK"
            )
            
            mock_monitor.check_database_health = AsyncMock(return_value=unhealthy_check)
            mock_monitor.check_llm_backend_health = AsyncMock(return_value=healthy_check)
            
            response = client.get("/api/v1/health/ready")
            assert response.status_code == 503
            data = response.json()["detail"]
            assert data["status"] == "not_ready"
    
    def test_health_live_endpoint(self, client):
        """Test liveness probe endpoint"""
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
    
    def test_health_detailed_endpoint(self, client):
        """Test detailed health check endpoint"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock comprehensive health check
            mock_system_health = SystemHealth(
                overall_status=HealthStatus.HEALTHY,
                health_score=0.95,
                component_checks=[
                    HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "DB OK"),
                    HealthCheck(ComponentType.REDIS, HealthStatus.HEALTHY, 50.0, "Redis OK"),
                    HealthCheck(ComponentType.LLM_BACKEND, HealthStatus.HEALTHY, 200.0, "LLM OK")
                ]
            )
            
            mock_monitor.perform_comprehensive_health_check = AsyncMock(
                return_value=mock_system_health
            )
            
            response = client.get("/api/v1/health/detailed")
            assert response.status_code == 200
            data = response.json()
            
            assert data["overall_status"] == "healthy"
            assert data["health_score"] == 0.95
            assert len(data["components"]) == 3
            assert data["healthy_components"] == 3
            assert data["total_components"] == 3
    
    def test_health_component_endpoint(self, client):
        """Test component-specific health endpoint"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock database health check
            db_check = HealthCheck(
                ComponentType.DATABASE,
                HealthStatus.HEALTHY,
                125.0,
                "Database connection healthy",
                {"connections": 8, "version": "PostgreSQL"}
            )
            mock_monitor.check_database_health = AsyncMock(return_value=db_check)
            
            response = client.get("/api/v1/health/component/database")
            assert response.status_code == 200
            data = response.json()
            
            assert data["component"] == "database"
            assert data["status"] == "healthy"
            assert data["response_time_ms"] == 125.0
            assert data["is_healthy"] is True
            assert "connections" in data["details"]
    
    def test_health_component_invalid(self, client):
        """Test invalid component health endpoint"""
        response = client.get("/api/v1/health/component/invalid")
        assert response.status_code == 400
        data = response.json()
        assert "Invalid component" in data["detail"]["error"]
        assert "valid_components" in data["detail"]
    
    def test_health_summary_endpoint(self, client):
        """Test health summary endpoint"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock last health check
            mock_system_health = SystemHealth(
                overall_status=HealthStatus.DEGRADED,
                health_score=0.75,
                component_checks=[
                    HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "DB OK"),
                    HealthCheck(ComponentType.REDIS, HealthStatus.DEGRADED, 600.0, "Redis slow"),
                    HealthCheck(ComponentType.LLM_BACKEND, HealthStatus.HEALTHY, 200.0, "LLM OK")
                ]
            )
            
            mock_monitor.get_last_health_check.return_value = mock_system_health
            mock_monitor.get_health_trends.return_value = {"trend": "degrading"}
            
            response = client.get("/api/v1/health/summary")
            assert response.status_code == 200
            data = response.json()
            
            assert data["overall_status"] == "degraded"
            assert data["health_score"] == 0.75
            assert data["healthy_components"] == 2
            assert data["total_components"] == 3
            assert data["trends"] == "degrading"
    
    def test_health_history_endpoint(self, client):
        """Test health history endpoint"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock health history
            history = [
                SystemHealth(HealthStatus.HEALTHY, 0.9, []),
                SystemHealth(HealthStatus.HEALTHY, 0.92, []),
                SystemHealth(HealthStatus.DEGRADED, 0.75, [])
            ]
            mock_monitor.get_health_history.return_value = history
            
            response = client.get("/api/v1/health/history?limit=5")
            assert response.status_code == 200
            data = response.json()
            
            assert data["count"] == 3
            assert data["limit"] == 5
            assert len(data["history"]) == 3
    
    def test_health_trends_endpoint(self, client):
        """Test health trends endpoint"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            mock_monitor.get_health_trends.return_value = {
                "time_period": "last_hour",
                "checks_count": 12,
                "average_health_score": 0.88,
                "component_uptime_percent": {
                    "database": 100.0,
                    "redis": 91.7,
                    "llm": 100.0
                },
                "trend": "stable"
            }
            
            response = client.get("/api/v1/health/trends")
            assert response.status_code == 200
            data = response.json()
            
            assert data["average_health_score"] == 0.88
            assert data["trend"] == "stable"
            assert "component_uptime_percent" in data
    
    def test_trigger_health_check_endpoint(self, client):
        """Test manual health check trigger endpoint"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            mock_system_health = SystemHealth(
                HealthStatus.HEALTHY, 0.95, []
            )
            mock_monitor.perform_comprehensive_health_check = AsyncMock(
                return_value=mock_system_health
            )
            
            response = client.post("/api/v1/health/check")
            assert response.status_code == 200
            data = response.json()
            
            assert data["message"] == "Health check completed"
            assert "triggered_at" in data
            assert data["overall_status"] == "healthy"


class TestAdminAPIEndpoints:
    """Test admin API endpoints"""
    
    def test_get_feature_flags_endpoint(self, client, mock_settings, mock_redis):
        """Test get all feature flags endpoint"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            # Mock feature manager response
            mock_redis.keys.return_value = ["flag:enable_hybrid_search"]
            mock_redis.get.return_value = "true"
            mock_redis.ttl.return_value = 1800
            
            response = client.get("/api/v1/admin/config/flags")
            assert response.status_code == 200
            data = response.json()
            
            # Should contain settings-based flags
            assert isinstance(data, dict)
            assert len(data) > 0
    
    def test_set_feature_flag_endpoint(self, client, mock_settings, mock_redis):
        """Test set feature flag endpoint"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            mock_redis.set.return_value = True
            
            response = client.post(
                "/api/v1/admin/config/flags/enable_hybrid_search",
                json={
                    "enabled": True,
                    "ttl_minutes": 60,
                    "reason": "Testing hybrid search functionality"
                }
            )
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "updated"
            assert data["flag"] == "enable_hybrid_search"
            assert data["value"] is True
            assert data["ttl_minutes"] == 60
            assert data["reason"] == "Testing hybrid search functionality"
    
    def test_set_feature_flag_production_safety(self, client, mock_redis):
        """Test feature flag safety in production"""
        # Mock production settings
        prod_settings = Mock()
        prod_settings.environment = "production"
        prod_settings.is_production = True
        prod_settings.features = Mock()
        prod_settings.features.enable_phi_scrubbing = True
        
        with patch('src.api.dependencies.get_enhanced_settings', return_value=prod_settings), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            # Should not allow disabling safety flag in production
            response = client.post(
                "/api/v1/admin/config/flags/enable_phi_scrubbing",
                json={"enabled": False, "ttl_minutes": 30}
            )
            assert response.status_code == 400
            data = response.json()
            assert "Failed to set feature flag" in data["detail"]
    
    def test_clear_flag_overrides_endpoint(self, client, mock_settings, mock_redis):
        """Test clear flag overrides endpoint"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            mock_redis.keys.return_value = ["flag:enable_hybrid_search", "flag:enable_elasticsearch"]
            mock_redis.delete.return_value = 2
            
            response = client.delete("/api/v1/admin/config/flags")
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "cleared"
            assert data["count"] == 2
            assert "temporary flag overrides" in data["message"]
    
    def test_get_single_flag_endpoint(self, client, mock_settings, mock_redis):
        """Test get single feature flag endpoint"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            mock_redis.keys.return_value = []
            
            response = client.get("/api/v1/admin/config/flags/enable_metrics")
            assert response.status_code == 200
            data = response.json()
            
            assert data["name"] == "enable_metrics"
            assert "current_value" in data
            assert "default_value" in data
    
    def test_get_single_flag_not_found(self, client, mock_settings, mock_redis):
        """Test get nonexistent feature flag"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            mock_redis.keys.return_value = []
            
            response = client.get("/api/v1/admin/config/flags/nonexistent_flag")
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["detail"]
    
    def test_configuration_summary_endpoint(self, client, mock_settings):
        """Test configuration summary endpoint"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings):
            response = client.get("/api/v1/admin/config/summary")
            assert response.status_code == 200
            data = response.json()
            
            assert data["environment"] == "integration_test"
            assert isinstance(data["enabled_features"], list)
            assert isinstance(data["configuration_warnings"], list)
            assert isinstance(data["backend_services"], dict)
    
    def test_validate_configuration_endpoint(self, client, mock_settings):
        """Test configuration validation endpoint"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings):
            response = client.get("/api/v1/admin/config/validate")
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "validated"
            assert "warnings_count" in data
            assert "warnings" in data
            assert data["environment"] == "integration_test"
            assert data["is_production"] is False
    
    def test_validate_flag_dependencies_endpoint(self, client, mock_settings, mock_redis):
        """Test flag dependency validation endpoint"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            response = client.post("/api/v1/admin/config/validate-dependencies")
            assert response.status_code == 200
            data = response.json()
            
            assert data["status"] == "validated"
            assert "dependency_warnings" in data
            assert "warnings_count" in data
    
    def test_get_feature_usage_stats_endpoint(self, client, mock_settings, mock_redis):
        """Test feature usage statistics endpoint"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            mock_redis.keys.return_value = ["flag:enable_hybrid_search"]
            
            response = client.get("/api/v1/admin/config/usage-stats")
            assert response.status_code == 200
            data = response.json()
            
            # Should return usage statistics structure
            assert isinstance(data, dict)
    
    def test_configuration_health_endpoint(self, client, mock_settings, mock_redis):
        """Test configuration health endpoint"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            mock_redis.ping.return_value = True
            
            response = client.get("/api/v1/admin/health/configuration")
            assert response.status_code == 200
            data = response.json()
            
            assert "status" in data
            assert data["status"] in ["healthy", "degraded", "unhealthy"]
            assert "flag_manager_healthy" in data
            assert "environment" in data


class TestAPIErrorHandling:
    """Test API error handling"""
    
    def test_health_endpoint_error_handling(self, client):
        """Test health endpoint error handling"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            mock_monitor.perform_comprehensive_health_check = AsyncMock(
                side_effect=Exception("Health check failed")
            )
            
            response = client.get("/api/v1/health/detailed")
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
    
    def test_admin_endpoint_error_handling(self, client, mock_settings):
        """Test admin endpoint error handling"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings), \
             patch('src.config.feature_manager.FeatureManager', side_effect=Exception("Feature manager error")):
            
            response = client.get("/api/v1/admin/config/flags")
            assert response.status_code == 503
            data = response.json()
            assert "Feature management service unavailable" in data["detail"]
    
    def test_metrics_endpoint_error_handling(self, client):
        """Test metrics endpoint error handling"""
        with patch('prometheus_client.generate_latest', side_effect=Exception("Prometheus error")):
            response = client.get("/metrics")
            assert response.status_code == 500
            assert "Error generating metrics" in response.text


class TestAPIIntegrationScenarios:
    """Test realistic API integration scenarios"""
    
    def test_complete_admin_workflow(self, client, mock_settings, mock_redis):
        """Test complete admin workflow"""
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            # 1. Get configuration summary
            response = client.get("/api/v1/admin/config/summary")
            assert response.status_code == 200
            summary = response.json()
            assert summary["environment"] == "integration_test"
            
            # 2. Validate configuration
            response = client.get("/api/v1/admin/config/validate")
            assert response.status_code == 200
            validation = response.json()
            assert validation["status"] == "validated"
            
            # 3. Get all feature flags
            mock_redis.keys.return_value = []
            response = client.get("/api/v1/admin/config/flags")
            assert response.status_code == 200
            flags = response.json()
            assert isinstance(flags, dict)
            
            # 4. Set a feature flag
            mock_redis.set.return_value = True
            response = client.post(
                "/api/v1/admin/config/flags/enable_hybrid_search",
                json={"enabled": True, "ttl_minutes": 30}
            )
            assert response.status_code == 200
            flag_update = response.json()
            assert flag_update["status"] == "updated"
            
            # 5. Get usage statistics
            mock_redis.keys.return_value = ["flag:enable_hybrid_search"]
            response = client.get("/api/v1/admin/config/usage-stats")
            assert response.status_code == 200
            stats = response.json()
            assert isinstance(stats, dict)
            
            # 6. Clear all overrides
            mock_redis.delete.return_value = 1
            response = client.delete("/api/v1/admin/config/flags")
            assert response.status_code == 200
            clear_result = response.json()
            assert clear_result["status"] == "cleared"
    
    def test_complete_health_monitoring_workflow(self, client):
        """Test complete health monitoring workflow"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock healthy system for most checks
            healthy_system_health = SystemHealth(
                HealthStatus.HEALTHY, 
                0.95,
                [
                    HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "DB OK"),
                    HealthCheck(ComponentType.REDIS, HealthStatus.HEALTHY, 50.0, "Redis OK"),
                    HealthCheck(ComponentType.LLM_BACKEND, HealthStatus.HEALTHY, 200.0, "LLM OK")
                ]
            )
            
            # 1. Check liveness
            response = client.get("/api/v1/health/live")
            assert response.status_code == 200
            
            # 2. Check readiness
            healthy_check = HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "OK")
            mock_monitor.check_database_health = AsyncMock(return_value=healthy_check)
            mock_monitor.check_llm_backend_health = AsyncMock(return_value=healthy_check)
            
            response = client.get("/api/v1/health/ready")
            assert response.status_code == 200
            
            # 3. Get detailed health
            mock_monitor.perform_comprehensive_health_check = AsyncMock(
                return_value=healthy_system_health
            )
            
            response = client.get("/api/v1/health/detailed")
            assert response.status_code == 200
            detailed = response.json()
            assert detailed["overall_status"] == "healthy"
            
            # 4. Get health summary
            mock_monitor.get_last_health_check.return_value = healthy_system_health
            mock_monitor.get_health_trends.return_value = {"trend": "stable"}
            
            response = client.get("/api/v1/health/summary")
            assert response.status_code == 200
            summary = response.json()
            assert summary["overall_status"] == "healthy"
            
            # 5. Trigger manual health check
            response = client.post("/api/v1/health/check")
            assert response.status_code == 200
            trigger_result = response.json()
            assert trigger_result["message"] == "Health check completed"
    
    def test_observability_integration_scenario(self, client):
        """Test complete observability integration"""
        # 1. Check metrics endpoint
        with patch('prometheus_client.generate_latest') as mock_generate:
            mock_generate.return_value = b"""
# HELP edbot_queries_total Total queries
edbot_queries_total{query_type="PROTOCOL_STEPS"} 45
edbot_system_health 0.95
edbot_safety_alerts_total{alert_type="low_confidence"} 2
"""
            response = client.get("/metrics")
            assert response.status_code == 200
            metrics_data = response.text
            assert "edbot_queries_total" in metrics_data
            assert "edbot_system_health" in metrics_data
        
        # 2. Check health status
        with patch('src.observability.health.health_monitor') as mock_monitor:
            mock_system_health = SystemHealth(HealthStatus.HEALTHY, 0.95, [])
            mock_monitor.get_last_health_check.return_value = mock_system_health
            
            response = client.get("/api/v1/health/status")
            assert response.status_code == 200
            status_data = response.json()
            assert status_data["status"] == "healthy"
            assert status_data["health_score"] == 0.95
        
        # 3. Check basic health endpoint
        with patch('src.observability.health.health_monitor') as mock_monitor:
            healthy_check = HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "OK")
            mock_monitor.check_database_health = AsyncMock(return_value=healthy_check)
            
            response = client.get("/health")
            assert response.status_code == 200
            basic_health = response.json()
            assert basic_health["service"] == "ed-bot-v8"
            assert basic_health["status"] == "healthy"


class TestAPIPerformance:
    """Test API performance with observability overhead"""
    
    def test_health_endpoint_performance(self, client):
        """Test health endpoint response times"""
        import time
        
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock fast health checks
            healthy_check = HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 50.0, "OK")
            mock_monitor.check_database_health = AsyncMock(return_value=healthy_check)
            
            # Time the request
            start_time = time.time()
            response = client.get("/api/v1/health/ready")
            end_time = time.time()
            
            assert response.status_code == 200
            # Health endpoint should respond quickly (< 1 second)
            assert (end_time - start_time) < 1.0
    
    def test_metrics_endpoint_performance(self, client):
        """Test metrics endpoint performance"""
        import time
        
        with patch('prometheus_client.generate_latest') as mock_generate:
            # Mock reasonable metrics payload
            mock_generate.return_value = b"edbot_queries_total 100" * 50  # Simulate multiple metrics
            
            start_time = time.time()
            response = client.get("/metrics")
            end_time = time.time()
            
            assert response.status_code == 200
            # Metrics endpoint should be fast (< 0.5 seconds)
            assert (end_time - start_time) < 0.5
    
    def test_admin_endpoint_performance(self, client, mock_settings, mock_redis):
        """Test admin endpoint performance"""
        import time
        
        with patch('src.api.dependencies.get_enhanced_settings', return_value=mock_settings), \
             patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            
            mock_redis.keys.return_value = []
            
            start_time = time.time()
            response = client.get("/api/v1/admin/config/flags")
            end_time = time.time()
            
            assert response.status_code == 200
            # Admin endpoints should respond quickly
            assert (end_time - start_time) < 1.0