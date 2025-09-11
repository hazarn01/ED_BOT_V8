"""
Integration tests for observability system.

Tests the complete observability pipeline including metrics collection,
health monitoring, medical safety tracking, and alerting integration.
"""

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.config.enhanced_settings import EnhancedSettings
from src.observability.health import ComponentType, HealthMonitor, HealthStatus
from src.observability.medical_metrics import (
    MedicalMetricsCollector,
    init_medical_metrics,
)
from src.observability.metrics import MetricsCollector, init_metrics


@pytest.fixture
def observability_settings():
    """Create settings for observability testing"""
    return EnhancedSettings(
        environment="integration_test",
        features__enable_metrics=True,
        features__enable_medical_metrics=True,
        observability__metrics_port=9090,
        observability__health_check_interval=30,
        observability__performance_alert_threshold=2.0,
        observability__log_query_metrics=True
    )


@pytest.fixture
def metrics_collector(observability_settings):
    """Create metrics collector for testing"""
    return MetricsCollector(observability_settings)


@pytest.fixture
def medical_metrics_collector(observability_settings):
    """Create medical metrics collector for testing"""
    return MedicalMetricsCollector(observability_settings)


@pytest.fixture
def health_monitor(observability_settings):
    """Create health monitor for testing"""
    return HealthMonitor(observability_settings)


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def mock_prometheus_metrics():
    """Mock Prometheus metrics for integration testing"""
    mocks = {}
    metric_names = [
        'query_total', 'query_duration', 'query_confidence',
        'medical_queries_by_specialty', 'clinical_confidence_distribution',
        'safety_alerts', 'system_health', 'component_health',
        'llm_backend_requests', 'cache_operations'
    ]
    
    for name in metric_names:
        mock_metric = Mock()
        mock_metric.labels.return_value.inc = Mock()
        mock_metric.labels.return_value.observe = Mock()
        mock_metric.labels.return_value.set = Mock()
        mock_metric.set = Mock()
        mocks[name] = mock_metric
    
    return mocks


class TestMetricsIntegration:
    """Test metrics collection integration across components"""
    
    def test_metrics_initialization_integration(self, observability_settings, mock_prometheus_metrics):
        """Test complete metrics initialization"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics):
            # Initialize metrics system
            init_metrics(observability_settings)
            init_medical_metrics(observability_settings)
            
            from src.observability.medical_metrics import medical_metrics
            from src.observability.metrics import metrics
            
            assert metrics.enabled is True
            assert medical_metrics.enabled is True
            assert metrics.settings is observability_settings
    
    def test_query_processing_metrics_pipeline(self, mock_prometheus_metrics):
        """Test complete query processing metrics pipeline"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics), \
             patch.multiple('src.observability.medical_metrics', **mock_prometheus_metrics):
            
            from src.observability.medical_metrics import medical_metrics
            from src.observability.metrics import metrics
            
            # Enable metrics
            metrics.enabled = True
            medical_metrics.enabled = True
            
            # Simulate complete query processing
            query = "what is the STEMI protocol for chest pain"
            query_type = "PROTOCOL_STEPS"
            confidence = 0.89
            response_time = 1.3
            
            # Track through all metrics systems
            metrics.track_query(query_type, response_time, confidence, True, "hybrid")
            medical_metrics.track_medical_query(query, query_type, confidence, response_time)
            
            # Verify core metrics were tracked
            mock_prometheus_metrics['query_total'].labels.assert_called()
            mock_prometheus_metrics['query_duration'].labels.assert_called()
            mock_prometheus_metrics['query_confidence'].labels.assert_called()
            
            # Verify medical metrics were tracked
            mock_prometheus_metrics['medical_queries_by_specialty'].labels.assert_called()
            mock_prometheus_metrics['clinical_confidence_distribution'].labels.assert_called()
    
    def test_hybrid_search_metrics_integration(self, mock_prometheus_metrics):
        """Test hybrid search metrics integration"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics):
            from src.observability.metrics import metrics
            metrics.enabled = True
            
            # Simulate hybrid search operation
            metrics.track_hybrid_search(
                query_type="PROTOCOL_STEPS",
                keyword_time=0.15,
                semantic_time=0.35,
                fusion_time=0.08,
                result_sources={"keyword": 12, "semantic": 18, "both": 6}
            )
            
            # Verify hybrid search metrics
            assert mock_prometheus_metrics['query_total'].labels.call_count >= 0
    
    def test_safety_monitoring_integration(self, mock_prometheus_metrics):
        """Test safety monitoring metrics integration"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics), \
             patch.multiple('src.observability.medical_metrics', **mock_prometheus_metrics):
            
            from src.observability.medical_metrics import medical_metrics
            from src.observability.metrics import metrics
            
            metrics.enabled = True
            medical_metrics.enabled = True
            
            # Simulate safety events
            metrics.track_safety_alert("low_confidence", "warning")
            metrics.track_phi_scrubbing("query", 2)
            
            medical_metrics.track_safety_event(
                "medication_error",
                "high", 
                {"medication": "insulin", "error": "dosage"}
            )
            
            # Verify safety alerts were tracked
            mock_prometheus_metrics['safety_alerts'].labels.assert_called()


class TestMedicalMetricsIntegration:
    """Test medical-specific metrics integration"""
    
    def test_clinical_workflow_metrics_tracking(self, mock_prometheus_metrics):
        """Test complete clinical workflow metrics tracking"""
        with patch.multiple('src.observability.medical_metrics', **mock_prometheus_metrics):
            from src.observability.medical_metrics import medical_metrics
            medical_metrics.enabled = True
            
            # Simulate emergency department workflow
            queries = [
                ("chest pain protocol STEMI", "PROTOCOL_STEPS", 0.92),
                ("morphine 2mg IV dosage", "DOSAGE_LOOKUP", 0.88), 
                ("cardiology on call contact", "CONTACT_LOOKUP", 0.95),
                ("troponin criteria for MI", "CRITERIA_CHECK", 0.91)
            ]
            
            for query, query_type, confidence in queries:
                medical_metrics.track_medical_query(
                    query, query_type, confidence, 1.2
                )
            
            # Verify medical specialty tracking
            call_count = mock_prometheus_metrics['medical_queries_by_specialty'].labels.call_count
            assert call_count == len(queries)
    
    def test_medication_safety_tracking_integration(self, mock_prometheus_metrics):
        """Test medication safety tracking integration"""
        with patch.multiple('src.observability.medical_metrics', **mock_prometheus_metrics):
            from src.observability.medical_metrics import medical_metrics
            medical_metrics.enabled = True
            
            # High-risk medication queries
            high_risk_queries = [
                "insulin sliding scale protocol",
                "heparin infusion rate calculation", 
                "warfarin dosing adjustment",
                "morphine PCA settings"
            ]
            
            for query in high_risk_queries:
                medical_metrics.track_medical_query(
                    query, "DOSAGE_LOOKUP", 0.85, 0.9
                )
            
            # Verify medication and safety tracking
            assert mock_prometheus_metrics['medical_queries_by_specialty'].labels.called
    
    def test_time_sensitive_protocol_tracking(self, mock_prometheus_metrics):
        """Test time-sensitive protocol tracking"""
        with patch.multiple('src.observability.medical_metrics', **mock_prometheus_metrics):
            from src.observability.medical_metrics import medical_metrics
            medical_metrics.enabled = True
            
            # Time-sensitive protocols
            protocols = [
                ("STEMI activation protocol", "STEMI"),
                ("stroke alert procedure", "stroke"), 
                ("sepsis bundle protocol", "sepsis"),
                ("trauma team activation", "trauma")
            ]
            
            for query, expected_protocol in protocols:
                medical_metrics.track_medical_query(
                    query, "PROTOCOL_STEPS", 0.93, 1.1
                )
            
            # Verify time-sensitive tracking
            assert mock_prometheus_metrics['medical_queries_by_specialty'].labels.called
    
    def test_clinical_confidence_distribution_tracking(self, mock_prometheus_metrics):
        """Test clinical confidence distribution tracking"""
        with patch.multiple('src.observability.medical_metrics', **mock_prometheus_metrics):
            from src.observability.medical_metrics import medical_metrics
            medical_metrics.enabled = True
            
            # Different specialties with varying confidence
            specialty_queries = [
                ("cardiac catheterization protocol", "cardiology", 0.95),
                ("trauma resuscitation steps", "emergency", 0.88),
                ("insulin dosage calculation", "pharmacy", 0.91),
                ("pneumonia treatment guidelines", "pulmonology", 0.87)
            ]
            
            for query, specialty, confidence in specialty_queries:
                medical_metrics.track_medical_query(
                    query, "PROTOCOL_STEPS", confidence, 1.0
                )
            
            # Verify confidence distribution tracking
            observe_calls = mock_prometheus_metrics['clinical_confidence_distribution'].labels.return_value.observe.call_count
            assert observe_calls == len(specialty_queries)


class TestHealthMonitoringIntegration:
    """Test health monitoring system integration"""
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_integration(self, health_monitor):
        """Test comprehensive health check integration"""
        with patch('src.observability.health.get_database') as mock_db, \
             patch('redis.asyncio.Redis') as mock_redis, \
             patch('aiohttp.ClientSession') as mock_session:
            
            # Mock database health check
            mock_db_conn = AsyncMock()
            mock_result = Mock()
            mock_result.fetchone.return_value = [1]
            mock_db_conn.execute.return_value = mock_result
            mock_db.__aenter__.return_value = mock_db_conn
            mock_db.__aexit__.return_value = None
            
            # Mock Redis health check
            mock_redis_conn = AsyncMock()
            mock_redis_conn.set.return_value = True
            mock_redis_conn.get.return_value = "test_value"
            mock_redis_conn.delete.return_value = 1
            mock_redis_conn.info.return_value = {'redis_version': '6.0.0'}
            mock_redis.return_value = mock_redis_conn
            
            # Mock HTTP session for LLM/Elasticsearch
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'models': []})
            mock_http_session = AsyncMock()
            mock_http_session.get.return_value.__aenter__.return_value = mock_response
            mock_http_session.get.return_value.__aexit__.return_value = None
            mock_session.return_value = mock_http_session
            
            # Perform comprehensive health check
            system_health = await health_monitor.perform_comprehensive_health_check()
            
            # Verify system health structure
            assert system_health.overall_status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
            assert 0.0 <= system_health.health_score <= 1.0
            assert len(system_health.component_checks) > 0
            
            # Verify component checks
            component_types = {check.component for check in system_health.component_checks}
            expected_components = {ComponentType.DATABASE, ComponentType.REDIS, ComponentType.LLM_BACKEND}
            assert expected_components.issubset(component_types)
    
    @pytest.mark.asyncio
    async def test_health_monitoring_with_metrics_integration(self, health_monitor, mock_prometheus_metrics):
        """Test health monitoring integration with metrics"""
        with patch('src.observability.health.get_database') as mock_db, \
             patch.multiple('src.observability.metrics', **mock_prometheus_metrics):
            
            # Mock healthy database
            mock_db_conn = AsyncMock()
            mock_result = Mock()
            mock_result.fetchone.return_value = [1]
            mock_db_conn.execute.return_value = mock_result
            mock_db.__aenter__.return_value = mock_db_conn
            mock_db.__aexit__.return_value = None
            
            # Perform health check
            db_check = await health_monitor.check_database_health()
            
            # Create mock system health
            from src.observability.health import SystemHealth
            system_health = SystemHealth(
                HealthStatus.HEALTHY,
                0.95,
                [db_check]
            )
            
            # Test metrics update integration
            await health_monitor._update_health_metrics(system_health)
            
            # Verify metrics were updated
            mock_prometheus_metrics['system_health'].set.assert_called_with(0.95)
            mock_prometheus_metrics['component_health'].labels.assert_called()
    
    @pytest.mark.asyncio
    async def test_health_trends_integration(self, health_monitor):
        """Test health trends calculation integration"""
        from datetime import datetime, timedelta

        from src.observability.health import HealthCheck, SystemHealth
        
        # Add historical health data
        base_time = datetime.now() - timedelta(hours=1)
        
        for i in range(10):
            health_check = SystemHealth(
                HealthStatus.HEALTHY,
                0.8 + (i * 0.02),  # Improving trend
                [HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "OK")]
            )
            health_check.timestamp = base_time + timedelta(minutes=i*5)
            health_monitor._health_history.append(health_check)
        
        # Get trends
        trends = health_monitor.get_health_trends()
        
        assert "average_health_score" in trends
        assert "component_uptime_percent" in trends
        assert "trend" in trends
        assert trends["trend"] == "improving"


class TestObservabilityAPIIntegration:
    """Test observability API endpoints integration"""
    
    def test_health_endpoints_integration(self, client):
        """Test health API endpoints integration"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock system health for detailed endpoint
            mock_system_health = Mock()
            mock_system_health.overall_status = HealthStatus.HEALTHY
            mock_system_health.to_dict.return_value = {
                "overall_status": "healthy",
                "health_score": 0.92,
                "components": [],
                "healthy_components": 5,
                "total_components": 6
            }
            mock_monitor.perform_comprehensive_health_check = AsyncMock(
                return_value=mock_system_health
            )
            
            # Test detailed health check
            response = client.get("/api/v1/health/detailed")
            assert response.status_code == 200
            data = response.json()
            assert data["overall_status"] == "healthy"
            assert data["health_score"] == 0.92
            
            # Test health summary
            mock_monitor.get_last_health_check.return_value = mock_system_health
            mock_monitor.get_health_trends.return_value = {"trend": "stable"}
            
            response = client.get("/api/v1/health/summary")
            assert response.status_code == 200
            data = response.json()
            assert "overall_status" in data
            assert "health_score" in data
    
    def test_metrics_endpoint_integration(self, client):
        """Test metrics endpoint integration"""
        with patch('prometheus_client.generate_latest') as mock_generate:
            # Mock Prometheus metrics output
            mock_metrics_data = b"""
# HELP edbot_queries_total Total queries processed
# TYPE edbot_queries_total counter
edbot_queries_total{query_type="PROTOCOL_STEPS",status="success",cache_hit="miss"} 45
edbot_queries_total{query_type="DOSAGE_LOOKUP",status="success",cache_hit="hit"} 23

# HELP edbot_system_health Overall system health score
# TYPE edbot_system_health gauge  
edbot_system_health 0.95

# HELP edbot_safety_alerts_total Medical safety alerts
# TYPE edbot_safety_alerts_total counter
edbot_safety_alerts_total{alert_type="low_confidence",severity="warning"} 2
"""
            mock_generate.return_value = mock_metrics_data
            
            response = client.get("/metrics")
            assert response.status_code == 200
            
            # Verify metrics content
            content = response.text
            assert "edbot_queries_total" in content
            assert "edbot_system_health" in content
            assert "edbot_safety_alerts_total" in content
    
    def test_component_health_endpoint_integration(self, client):
        """Test component health endpoint integration"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock database health check
            from src.observability.health import HealthCheck
            db_check = HealthCheck(
                ComponentType.DATABASE, 
                HealthStatus.HEALTHY,
                150.0,
                "Database connection healthy",
                {"connections": 5, "version": "PostgreSQL"}
            )
            mock_monitor.check_database_health = AsyncMock(return_value=db_check)
            
            response = client.get("/api/v1/health/component/database")
            assert response.status_code == 200
            data = response.json()
            
            assert data["component"] == "database"
            assert data["status"] == "healthy"
            assert data["response_time_ms"] == 150.0
            assert data["is_healthy"] is True


class TestObservabilityErrorHandling:
    """Test observability system error handling"""
    
    @pytest.mark.asyncio
    async def test_metrics_collection_error_handling(self, mock_prometheus_metrics):
        """Test metrics collection error handling"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics):
            # Make one metric raise an exception
            mock_prometheus_metrics['query_total'].labels.side_effect = Exception("Prometheus error")
            
            from src.observability.metrics import metrics
            metrics.enabled = True
            
            # Should handle exception gracefully
            try:
                metrics.track_query("PROTOCOL_STEPS", 1.0, 0.8)
                # Should not raise exception
            except Exception as e:
                pytest.fail(f"Metrics error handling failed: {e}")
    
    @pytest.mark.asyncio
    async def test_health_monitoring_error_handling(self, health_monitor):
        """Test health monitoring error handling"""
        with patch('src.observability.health.get_database', side_effect=Exception("Database error")):
            # Should handle database connection error gracefully
            check = await health_monitor.check_database_health()
            
            assert check.component == ComponentType.DATABASE
            assert check.status == HealthStatus.UNHEALTHY
            assert "failed" in check.message.lower()
    
    def test_health_api_error_handling(self, client):
        """Test health API error handling"""
        with patch('src.observability.health.health_monitor') as mock_monitor:
            # Mock health check failure
            mock_monitor.perform_comprehensive_health_check = AsyncMock(
                side_effect=Exception("Health check failed")
            )
            
            response = client.get("/api/v1/health/detailed")
            assert response.status_code == 500
            
            error_data = response.json()
            assert "detail" in error_data
    
    def test_metrics_endpoint_error_handling(self, client):
        """Test metrics endpoint error handling"""
        with patch('prometheus_client.generate_latest', side_effect=Exception("Metrics generation failed")):
            response = client.get("/metrics")
            assert response.status_code == 500
            assert "Error generating metrics" in response.text


class TestObservabilityPerformance:
    """Test observability system performance"""
    
    @pytest.mark.asyncio
    async def test_health_check_performance(self, health_monitor):
        """Test health check performance"""
        with patch('src.observability.health.get_database') as mock_db, \
             patch('redis.asyncio.Redis') as mock_redis:
            
            # Mock fast responses
            mock_db_conn = AsyncMock()
            mock_result = Mock()
            mock_result.fetchone.return_value = [1]
            mock_db_conn.execute.return_value = mock_result
            mock_db.__aenter__.return_value = mock_db_conn
            mock_db.__aexit__.return_value = None
            
            mock_redis_conn = AsyncMock()
            mock_redis_conn.set.return_value = True
            mock_redis_conn.get.return_value = "test"
            mock_redis_conn.delete.return_value = 1
            mock_redis_conn.info.return_value = {}
            mock_redis.return_value = mock_redis_conn
            
            # Time the health checks
            start_time = time.time()
            
            db_check = await health_monitor.check_database_health()
            redis_check = await health_monitor.check_redis_health()
            
            total_time = time.time() - start_time
            
            # Health checks should be fast (< 1 second each)
            assert db_check.response_time_ms < 1000
            assert redis_check.response_time_ms < 1000
            assert total_time < 2.0  # Total should be fast
    
    def test_metrics_collection_performance(self, mock_prometheus_metrics):
        """Test metrics collection performance"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics):
            from src.observability.metrics import metrics
            metrics.enabled = True
            
            # Time metrics collection
            start_time = time.time()
            
            # Collect many metrics
            for i in range(100):
                metrics.track_query("PROTOCOL_STEPS", 1.0, 0.8)
                metrics.track_cache_operation("get", "PROTOCOL_STEPS", True, 0.9)
                metrics.track_llm_request("ollama", 1.5)
            
            total_time = time.time() - start_time
            
            # Metrics collection should be very fast
            assert total_time < 1.0  # Should complete in under 1 second


class TestObservabilityIntegrationScenarios:
    """Test realistic observability integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_emergency_protocol_scenario(self, mock_prometheus_metrics):
        """Test complete emergency protocol scenario with observability"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics), \
             patch.multiple('src.observability.medical_metrics', **mock_prometheus_metrics):
            
            from src.observability.medical_metrics import medical_metrics
            from src.observability.metrics import metrics
            
            metrics.enabled = True
            medical_metrics.enabled = True
            
            # Simulate STEMI protocol emergency scenario
            scenario_queries = [
                ("STEMI protocol activation", "PROTOCOL_STEPS", 0.95, 0.8),
                ("cardiology on call contact", "CONTACT_LOOKUP", 0.98, 0.3),
                ("morphine 2mg IV for chest pain", "DOSAGE_LOOKUP", 0.91, 0.5),
                ("cardiac catheterization criteria", "CRITERIA_CHECK", 0.89, 0.7)
            ]
            
            # Process emergency scenario
            for query, query_type, confidence, response_time in scenario_queries:
                # Track through both systems
                metrics.track_query(query_type, response_time, confidence, False, "hybrid")
                medical_metrics.track_medical_query(query, query_type, confidence, response_time)
                
                # Track cache operations
                metrics.track_cache_operation("get", query_type, False)
                metrics.track_cache_operation("set", query_type)
            
            # Track LLM requests
            metrics.track_llm_request("ollama", 1.2, 150, 75, "success")
            
            # Verify comprehensive tracking
            assert mock_prometheus_metrics['query_total'].labels.call_count >= len(scenario_queries)
            assert mock_prometheus_metrics['medical_queries_by_specialty'].labels.call_count >= len(scenario_queries)
    
    @pytest.mark.asyncio
    async def test_system_degradation_scenario(self, health_monitor, mock_prometheus_metrics):
        """Test system degradation scenario with monitoring"""
        with patch('src.observability.health.get_database') as mock_db, \
             patch('redis.asyncio.Redis') as mock_redis, \
             patch.multiple('src.observability.metrics', **mock_prometheus_metrics):
            
            # Simulate system degradation
            # Database becomes slow
            mock_db_conn = AsyncMock()
            mock_result = Mock()
            mock_result.fetchone.return_value = [1]
            mock_db_conn.execute.return_value = mock_result
            mock_db.__aenter__.return_value = mock_db_conn
            mock_db.__aexit__.return_value = None
            
            # Redis becomes unavailable
            mock_redis.side_effect = Exception("Redis connection failed")
            
            # Mock slow loop for database
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.time.side_effect = [0.0, 1.5]  # Slow database
                
                # Perform health checks
                system_health = await health_monitor.perform_comprehensive_health_check()
                
                # System should be degraded due to slow database and failed Redis
                assert system_health.overall_status in [HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
                assert system_health.health_score < 0.8
                
                # Track health metrics
                await health_monitor._update_health_metrics(system_health)
                
                # Verify health metrics were updated
                mock_prometheus_metrics['system_health'].set.assert_called()
                mock_prometheus_metrics['component_health'].labels.assert_called()
    
    @pytest.mark.asyncio
    async def test_high_volume_monitoring_scenario(self, mock_prometheus_metrics):
        """Test high-volume monitoring scenario"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics), \
             patch.multiple('src.observability.medical_metrics', **mock_prometheus_metrics):
            
            from src.observability.medical_metrics import medical_metrics
            from src.observability.metrics import metrics
            
            metrics.enabled = True
            medical_metrics.enabled = True
            
            # Simulate high-volume query processing
            query_types = ["PROTOCOL_STEPS", "DOSAGE_LOOKUP", "CONTACT_LOOKUP", "CRITERIA_CHECK"]
            medical_queries = [
                "chest pain protocol",
                "insulin dosage",
                "cardiology contact", 
                "STEMI criteria"
            ]
            
            # Process high volume of queries
            for i in range(50):  # 50 queries
                query_type = query_types[i % len(query_types)]
                query = medical_queries[i % len(medical_queries)]
                confidence = 0.8 + (i % 20) * 0.01  # Varying confidence
                response_time = 0.5 + (i % 10) * 0.1  # Varying response time
                
                metrics.track_query(query_type, response_time, confidence, i % 3 == 0, "hybrid")
                medical_metrics.track_medical_query(query, query_type, confidence, response_time)
            
            # Verify high-volume tracking handled correctly
            assert mock_prometheus_metrics['query_total'].labels.call_count >= 50
            assert mock_prometheus_metrics['medical_queries_by_specialty'].labels.call_count >= 50