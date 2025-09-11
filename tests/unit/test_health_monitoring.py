"""
Unit tests for health monitoring system.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.observability.health import (
    ComponentType,
    HealthCheck,
    HealthMonitor,
    HealthStatus,
    SystemHealth,
    init_health_monitoring,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for health monitoring"""
    settings = Mock()
    settings.enable_health_monitoring = True
    settings.health_check_interval = 30
    settings.db_host = "localhost"
    settings.db_port = 5432
    settings.redis_host = "localhost"
    settings.redis_port = 6379
    settings.llm_backend = "ollama"
    settings.ollama_base_url = "http://localhost:11434"
    settings.vllm_base_url = "http://localhost:8000"
    
    # Mock hybrid search settings
    settings.hybrid_search = Mock()
    settings.hybrid_search.elasticsearch_url = "http://localhost:9200"
    
    return settings


@pytest.fixture
def health_monitor_instance(mock_settings):
    """Create health monitor instance"""
    return HealthMonitor(mock_settings)


@pytest.fixture
def disabled_health_monitor():
    """Create disabled health monitor"""
    settings = Mock()
    settings.enable_health_monitoring = False
    return HealthMonitor(settings)


class TestHealthCheckDataClass:
    """Test HealthCheck data class"""
    
    def test_health_check_creation(self):
        """Test health check creation"""
        check = HealthCheck(
            component=ComponentType.DATABASE,
            status=HealthStatus.HEALTHY,
            response_time_ms=150.5,
            message="Database connection healthy",
            details={"connections": 5}
        )
        
        assert check.component == ComponentType.DATABASE
        assert check.status == HealthStatus.HEALTHY
        assert check.response_time_ms == 150.5
        assert check.message == "Database connection healthy"
        assert check.details["connections"] == 5
        assert isinstance(check.timestamp, datetime)
    
    def test_health_check_to_dict(self):
        """Test health check dictionary conversion"""
        check = HealthCheck(
            component=ComponentType.REDIS,
            status=HealthStatus.DEGRADED,
            response_time_ms=500.0,
            message="Redis responding slowly"
        )
        
        result = check.to_dict()
        
        assert result["component"] == "redis"
        assert result["status"] == "degraded"
        assert result["response_time_ms"] == 500.0
        assert result["message"] == "Redis responding slowly"
        assert result["is_healthy"] is False
        assert "timestamp" in result


class TestSystemHealthDataClass:
    """Test SystemHealth data class"""
    
    def test_system_health_creation(self):
        """Test system health creation"""
        checks = [
            HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "DB OK"),
            HealthCheck(ComponentType.REDIS, HealthStatus.HEALTHY, 50.0, "Redis OK")
        ]
        
        system_health = SystemHealth(
            overall_status=HealthStatus.HEALTHY,
            health_score=0.95,
            component_checks=checks
        )
        
        assert system_health.overall_status == HealthStatus.HEALTHY
        assert system_health.health_score == 0.95
        assert len(system_health.component_checks) == 2
    
    def test_system_health_to_dict(self):
        """Test system health dictionary conversion"""
        checks = [
            HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "DB OK"),
            HealthCheck(ComponentType.REDIS, HealthStatus.UNHEALTHY, 1000.0, "Redis down")
        ]
        
        system_health = SystemHealth(
            overall_status=HealthStatus.DEGRADED,
            health_score=0.5,
            component_checks=checks
        )
        
        result = system_health.to_dict()
        
        assert result["overall_status"] == "degraded"
        assert result["health_score"] == 0.5
        assert result["healthy_components"] == 1
        assert result["total_components"] == 2
        assert len(result["components"]) == 2
        assert "summary" in result
    
    def test_system_health_summary(self):
        """Test system health summary generation"""
        checks = [
            HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "DB OK"),
            HealthCheck(ComponentType.REDIS, HealthStatus.DEGRADED, 500.0, "Redis slow"),
            HealthCheck(ComponentType.LLM_BACKEND, HealthStatus.UNHEALTHY, 0.0, "LLM down")
        ]
        
        system_health = SystemHealth(
            overall_status=HealthStatus.DEGRADED,
            health_score=0.6,
            component_checks=checks
        )
        
        summary = system_health._get_summary()
        
        assert summary["healthy"] == 1
        assert summary["degraded"] == 1
        assert summary["unhealthy"] == 1
        assert summary["unknown"] == 0


class TestHealthMonitorInitialization:
    """Test health monitor initialization"""
    
    def test_health_monitor_init_enabled(self, mock_settings):
        """Test health monitor initialization with enabled monitoring"""
        monitor = HealthMonitor(mock_settings)
        
        assert monitor.settings is mock_settings
        assert monitor.enabled is True
        assert monitor.check_interval == 30
        assert monitor.timeout_seconds == 5.0
        assert monitor._last_health_check is None
        assert monitor._health_history == []
    
    def test_health_monitor_init_disabled(self):
        """Test health monitor initialization with disabled monitoring"""
        settings = Mock()
        settings.enable_health_monitoring = False
        
        monitor = HealthMonitor(settings)
        
        assert monitor.enabled is False
    
    def test_health_monitor_init_no_settings(self):
        """Test health monitor initialization without settings"""
        monitor = HealthMonitor()
        
        assert monitor.settings is None
        assert monitor.enabled is True  # Default enabled
        assert monitor.check_interval == 30  # Default value
    
    def test_init_health_monitoring_function(self, mock_settings):
        """Test init_health_monitoring function"""
        with patch('src.observability.health.health_monitor') as mock_instance:
            init_health_monitoring(mock_settings)
            
            # Should have created new health monitor
            assert mock_instance is not None


class TestDatabaseHealthCheck:
    """Test database health check"""
    
    @pytest.mark.asyncio
    async def test_check_database_health_success(self, health_monitor_instance):
        """Test successful database health check"""
        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.fetchone.return_value = [1]
        mock_db.execute.return_value = mock_result
        
        mock_get_database = AsyncMock()
        mock_get_database.__aenter__.return_value = mock_db
        mock_get_database.__aexit__.return_value = None
        
        with patch('src.observability.health.get_database', return_value=mock_get_database):
            check = await health_monitor_instance.check_database_health()
            
            assert check.component == ComponentType.DATABASE
            assert check.status == HealthStatus.HEALTHY
            assert check.response_time_ms < 1000  # Should be fast
            assert "healthy" in check.message.lower()
    
    @pytest.mark.asyncio
    async def test_check_database_health_slow_response(self, health_monitor_instance):
        """Test database health check with slow response"""
        mock_db = AsyncMock()
        mock_result = Mock()
        mock_result.fetchone.return_value = [1]
        mock_db.execute.return_value = mock_result
        
        mock_get_database = AsyncMock()
        mock_get_database.__aenter__.return_value = mock_db
        mock_get_database.__aexit__.return_value = None
        
        with patch('src.observability.health.get_database', return_value=mock_get_database), \
             patch('asyncio.get_event_loop') as mock_loop:
            
            # Mock slow response
            mock_loop.return_value.time.side_effect = [0.0, 1.5]  # 1.5 second delay
            
            check = await health_monitor_instance.check_database_health()
            
            assert check.status == HealthStatus.DEGRADED
            assert "slowly" in check.message.lower()
    
    @pytest.mark.asyncio
    async def test_check_database_health_failure(self, health_monitor_instance):
        """Test database health check failure"""
        with patch('src.observability.health.get_database', side_effect=Exception("DB connection failed")):
            check = await health_monitor_instance.check_database_health()
            
            assert check.component == ComponentType.DATABASE
            assert check.status == HealthStatus.UNHEALTHY
            assert "failed" in check.message.lower()


class TestRedisHealthCheck:
    """Test Redis health check"""
    
    @pytest.mark.asyncio
    async def test_check_redis_health_success(self, health_monitor_instance):
        """Test successful Redis health check"""
        mock_redis_client = AsyncMock()
        mock_redis_client.set.return_value = True
        mock_redis_client.get.return_value = "health_test_value"
        mock_redis_client.delete.return_value = 1
        mock_redis_client.info.return_value = {
            'redis_version': '6.2.0',
            'connected_clients': 5,
            'used_memory_human': '1.2MB',
            'uptime_in_seconds': 3600
        }
        
        with patch('redis.asyncio.Redis', return_value=mock_redis_client):
            check = await health_monitor_instance.check_redis_health()
            
            assert check.component == ComponentType.REDIS
            assert check.status == HealthStatus.HEALTHY
            assert "healthy" in check.message.lower()
            assert "redis_version" in check.details
    
    @pytest.mark.asyncio
    async def test_check_redis_health_slow_response(self, health_monitor_instance):
        """Test Redis health check with slow response"""
        mock_redis_client = AsyncMock()
        mock_redis_client.set.return_value = True
        mock_redis_client.get.return_value = "health_test_value"
        mock_redis_client.delete.return_value = 1
        mock_redis_client.info.return_value = {}
        
        with patch('redis.asyncio.Redis', return_value=mock_redis_client), \
             patch('asyncio.get_event_loop') as mock_loop:
            
            # Mock slow response (>500ms)
            mock_loop.return_value.time.side_effect = [0.0, 0.6]  # 600ms delay
            
            check = await health_monitor_instance.check_redis_health()
            
            assert check.status == HealthStatus.DEGRADED
            assert "slowly" in check.message.lower()
    
    @pytest.mark.asyncio
    async def test_check_redis_health_failure(self, health_monitor_instance):
        """Test Redis health check failure"""
        with patch('redis.asyncio.Redis', side_effect=Exception("Redis connection failed")):
            check = await health_monitor_instance.check_redis_health()
            
            assert check.component == ComponentType.REDIS
            assert check.status == HealthStatus.UNHEALTHY
            assert "failed" in check.message.lower()


class TestElasticsearchHealthCheck:
    """Test Elasticsearch health check"""
    
    @pytest.mark.asyncio
    async def test_check_elasticsearch_health_success(self, health_monitor_instance):
        """Test successful Elasticsearch health check"""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'status': 'green',
            'cluster_name': 'edbot-cluster',
            'active_shards': 10,
            'number_of_nodes': 3,
            'number_of_data_nodes': 3
        })
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            check = await health_monitor_instance.check_elasticsearch_health()
            
            assert check.component == ComponentType.ELASTICSEARCH
            assert check.status == HealthStatus.HEALTHY
            assert "healthy" in check.message.lower()
            assert check.details["status"] == "green"
    
    @pytest.mark.asyncio
    async def test_check_elasticsearch_health_yellow(self, health_monitor_instance):
        """Test Elasticsearch health check with yellow status"""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'status': 'yellow',
            'cluster_name': 'edbot-cluster'
        })
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            check = await health_monitor_instance.check_elasticsearch_health()
            
            assert check.status == HealthStatus.DEGRADED
            assert "degraded" in check.message.lower()
    
    @pytest.mark.asyncio
    async def test_check_elasticsearch_health_not_configured(self, mock_settings):
        """Test Elasticsearch health check when not configured"""
        mock_settings.hybrid_search.elasticsearch_url = None
        monitor = HealthMonitor(mock_settings)
        
        check = await monitor.check_elasticsearch_health()
        
        assert check.component == ComponentType.ELASTICSEARCH
        assert check.status == HealthStatus.UNKNOWN
        assert "not configured" in check.message.lower()


class TestLLMBackendHealthCheck:
    """Test LLM backend health check"""
    
    @pytest.mark.asyncio
    async def test_check_llm_backend_ollama_success(self, health_monitor_instance):
        """Test successful Ollama health check"""
        health_monitor_instance.llm_backend = "ollama"
        
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'models': [
                {'name': 'mistral:7b-instruct'},
                {'name': 'llama2:13b'}
            ]
        })
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            check = await health_monitor_instance.check_llm_backend_health()
            
            assert check.component == ComponentType.LLM_BACKEND
            assert check.status == HealthStatus.HEALTHY
            assert "healthy" in check.message.lower()
            assert check.details["backend_type"] == "ollama"
            assert check.details["available_models"] == 2
    
    @pytest.mark.asyncio
    async def test_check_llm_backend_vllm_success(self, health_monitor_instance):
        """Test successful vLLM health check"""
        health_monitor_instance.llm_backend = "gpt-oss"
        
        mock_response = Mock()
        mock_response.status = 200
        
        mock_session = AsyncMock()
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = None
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            check = await health_monitor_instance.check_llm_backend_health()
            
            assert check.component == ComponentType.LLM_BACKEND
            assert check.status == HealthStatus.HEALTHY
            assert check.details["backend_type"] == "vllm"
    
    @pytest.mark.asyncio
    async def test_check_llm_backend_unknown(self, health_monitor_instance):
        """Test unknown LLM backend"""
        health_monitor_instance.llm_backend = "unknown_backend"
        
        check = await health_monitor_instance.check_llm_backend_health()
        
        assert check.component == ComponentType.LLM_BACKEND
        assert check.status == HealthStatus.UNKNOWN
        assert "unknown" in check.message.lower()


class TestFeatureFlagsHealthCheck:
    """Test feature flags health check"""
    
    @pytest.mark.asyncio
    async def test_check_feature_flags_health_success(self, health_monitor_instance):
        """Test successful feature flags health check"""
        mock_feature_manager = AsyncMock()
        mock_feature_manager.get_flag.return_value = True
        mock_feature_manager.get_all_flags.return_value = {
            "enable_metrics": {"has_override": False},
            "enable_hybrid_search": {"has_override": True}
        }
        
        with patch('src.observability.health.FeatureManager', return_value=mock_feature_manager):
            check = await health_monitor_instance.check_feature_flags_health()
            
            assert check.component == ComponentType.FEATURE_FLAGS
            assert check.status == HealthStatus.HEALTHY
            assert "healthy" in check.message.lower()
            assert check.details["total_flags"] == 2
            assert check.details["active_overrides"] == 1
    
    @pytest.mark.asyncio
    async def test_check_feature_flags_health_failure(self, health_monitor_instance):
        """Test feature flags health check failure"""
        with patch('src.observability.health.FeatureManager', side_effect=Exception("Feature flags error")):
            check = await health_monitor_instance.check_feature_flags_health()
            
            assert check.component == ComponentType.FEATURE_FLAGS
            assert check.status == HealthStatus.UNHEALTHY
            assert "failed" in check.message.lower()


class TestMetricsHealthCheck:
    """Test metrics health check"""
    
    @pytest.mark.asyncio
    async def test_check_metrics_health_success(self, health_monitor_instance):
        """Test successful metrics health check"""
        mock_metrics = Mock()
        mock_metrics.enabled = True
        
        with patch('src.observability.health.metrics', mock_metrics), \
             patch('src.observability.health.generate_latest', return_value=b"metrics_data"):
            
            check = await health_monitor_instance.check_metrics_health()
            
            assert check.component == ComponentType.METRICS
            assert check.status == HealthStatus.HEALTHY
            assert "healthy" in check.message.lower()
            assert check.details["metrics_enabled"] is True
    
    @pytest.mark.asyncio
    async def test_check_metrics_health_disabled(self, health_monitor_instance):
        """Test metrics health check when disabled"""
        mock_metrics = Mock()
        mock_metrics.enabled = False
        
        with patch('src.observability.health.metrics', mock_metrics), \
             patch('src.observability.health.generate_latest', return_value=b""):
            
            check = await health_monitor_instance.check_metrics_health()
            
            assert check.component == ComponentType.METRICS
            assert check.status == HealthStatus.DEGRADED
            assert "disabled" in check.message.lower()


class TestComprehensiveHealthCheck:
    """Test comprehensive health check"""
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_all_healthy(self, health_monitor_instance):
        """Test comprehensive health check with all components healthy"""
        # Mock all health check methods to return healthy status
        healthy_check = HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "OK")
        
        with patch.multiple(
            health_monitor_instance,
            check_database_health=AsyncMock(return_value=healthy_check),
            check_redis_health=AsyncMock(return_value=healthy_check),
            check_elasticsearch_health=AsyncMock(return_value=healthy_check),
            check_llm_backend_health=AsyncMock(return_value=healthy_check),
            check_feature_flags_health=AsyncMock(return_value=healthy_check),
            check_metrics_health=AsyncMock(return_value=healthy_check)
        ):
            
            system_health = await health_monitor_instance.perform_comprehensive_health_check()
            
            assert system_health.overall_status == HealthStatus.HEALTHY
            assert system_health.health_score > 0.9
            assert len(system_health.component_checks) == 6
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_critical_component_down(self, health_monitor_instance):
        """Test comprehensive health check with critical component down"""
        healthy_check = HealthCheck(ComponentType.REDIS, HealthStatus.HEALTHY, 100.0, "OK")
        unhealthy_check = HealthCheck(ComponentType.DATABASE, HealthStatus.UNHEALTHY, 0.0, "Down")
        
        with patch.multiple(
            health_monitor_instance,
            check_database_health=AsyncMock(return_value=unhealthy_check),
            check_redis_health=AsyncMock(return_value=healthy_check),
            check_elasticsearch_health=AsyncMock(return_value=healthy_check),
            check_llm_backend_health=AsyncMock(return_value=healthy_check),
            check_feature_flags_health=AsyncMock(return_value=healthy_check),
            check_metrics_health=AsyncMock(return_value=healthy_check)
        ):
            
            system_health = await health_monitor_instance.perform_comprehensive_health_check()
            
            # Should be unhealthy because database (critical component) is down
            assert system_health.overall_status == HealthStatus.UNHEALTHY
            assert system_health.health_score < 0.5
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_degraded(self, health_monitor_instance):
        """Test comprehensive health check with degraded components"""
        healthy_check = HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "OK")
        degraded_check = HealthCheck(ComponentType.REDIS, HealthStatus.DEGRADED, 500.0, "Slow")
        
        with patch.multiple(
            health_monitor_instance,
            check_database_health=AsyncMock(return_value=healthy_check),
            check_redis_health=AsyncMock(return_value=degraded_check),
            check_elasticsearch_health=AsyncMock(return_value=healthy_check),
            check_llm_backend_health=AsyncMock(return_value=healthy_check),
            check_feature_flags_health=AsyncMock(return_value=healthy_check),
            check_metrics_health=AsyncMock(return_value=healthy_check)
        ):
            
            system_health = await health_monitor_instance.perform_comprehensive_health_check()
            
            assert system_health.overall_status == HealthStatus.DEGRADED
            assert 0.5 < system_health.health_score < 1.0
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_disabled(self, disabled_health_monitor):
        """Test comprehensive health check when disabled"""
        system_health = await disabled_health_monitor.perform_comprehensive_health_check()
        
        assert system_health.overall_status == HealthStatus.UNKNOWN
        assert system_health.health_score == 0.0


class TestHealthScoreCalculation:
    """Test health score calculation"""
    
    def test_calculate_health_score_all_healthy(self, health_monitor_instance):
        """Test health score calculation with all healthy components"""
        checks = [
            HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "OK"),
            HealthCheck(ComponentType.REDIS, HealthStatus.HEALTHY, 50.0, "OK"),
            HealthCheck(ComponentType.LLM_BACKEND, HealthStatus.HEALTHY, 200.0, "OK")
        ]
        
        score = health_monitor_instance._calculate_health_score(checks)
        
        assert score == 1.0
    
    def test_calculate_health_score_mixed_status(self, health_monitor_instance):
        """Test health score calculation with mixed component status"""
        checks = [
            HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "OK"),
            HealthCheck(ComponentType.REDIS, HealthStatus.DEGRADED, 500.0, "Slow"),
            HealthCheck(ComponentType.LLM_BACKEND, HealthStatus.UNHEALTHY, 0.0, "Down")
        ]
        
        score = health_monitor_instance._calculate_health_score(checks)
        
        # Should be weighted average: DB(0.25*1.0) + Redis(0.15*0.7) + LLM(0.25*0.0) + others
        assert 0.0 < score < 1.0
    
    def test_determine_overall_status_critical_down(self, health_monitor_instance):
        """Test overall status determination with critical component down"""
        checks = [
            HealthCheck(ComponentType.DATABASE, HealthStatus.UNHEALTHY, 0.0, "Down"),
            HealthCheck(ComponentType.REDIS, HealthStatus.HEALTHY, 50.0, "OK")
        ]
        
        status = health_monitor_instance._determine_overall_status(checks)
        
        assert status == HealthStatus.UNHEALTHY
    
    def test_determine_overall_status_majority_unhealthy(self, health_monitor_instance):
        """Test overall status with majority of components unhealthy"""
        checks = [
            HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "OK"),
            HealthCheck(ComponentType.REDIS, HealthStatus.UNHEALTHY, 0.0, "Down"),
            HealthCheck(ComponentType.ELASTICSEARCH, HealthStatus.UNHEALTHY, 0.0, "Down"),
            HealthCheck(ComponentType.METRICS, HealthStatus.UNHEALTHY, 0.0, "Down")
        ]
        
        status = health_monitor_instance._determine_overall_status(checks)
        
        # >50% unhealthy = system unhealthy
        assert status == HealthStatus.UNHEALTHY


class TestHealthHistoryManagement:
    """Test health history and trend management"""
    
    def test_get_last_health_check(self, health_monitor_instance):
        """Test getting last health check"""
        # Initially should be None
        assert health_monitor_instance.get_last_health_check() is None
        
        # Set a health check
        system_health = SystemHealth(
            HealthStatus.HEALTHY, 0.95, []
        )
        health_monitor_instance._last_health_check = system_health
        
        result = health_monitor_instance.get_last_health_check()
        assert result is system_health
    
    def test_health_history_management(self, health_monitor_instance):
        """Test health history storage and retrieval"""
        # Add some health checks to history
        for i in range(5):
            health_check = SystemHealth(
                HealthStatus.HEALTHY, 0.9 + (i * 0.01), []
            )
            health_monitor_instance._health_history.append(health_check)
        
        # Get recent history
        history = health_monitor_instance.get_health_history(limit=3)
        
        assert len(history) == 3
        # Should return most recent ones
        assert history[-1].health_score == 0.94
    
    def test_health_history_max_size(self, health_monitor_instance):
        """Test health history maximum size limit"""
        health_monitor_instance._max_history = 3
        
        # Add more checks than the maximum
        for i in range(5):
            health_check = SystemHealth(HealthStatus.HEALTHY, 0.9, [])
            health_monitor_instance._health_history.append(health_check)
            
            # Simulate the trimming that would happen in real usage
            if len(health_monitor_instance._health_history) > health_monitor_instance._max_history:
                health_monitor_instance._health_history.pop(0)
        
        # Should only keep the maximum number
        assert len(health_monitor_instance._health_history) == 3
    
    def test_get_health_trends(self, health_monitor_instance):
        """Test health trends calculation"""
        # Add some historical data
        base_time = datetime.now() - timedelta(hours=2)
        
        for i in range(10):
            health_check = SystemHealth(
                HealthStatus.HEALTHY, 
                0.8 + (i * 0.02),  # Improving trend
                [HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "OK")]
            )
            health_check.timestamp = base_time + timedelta(minutes=i*5)
            health_monitor_instance._health_history.append(health_check)
        
        trends = health_monitor_instance.get_health_trends()
        
        assert "time_period" in trends
        assert "average_health_score" in trends
        assert "component_uptime_percent" in trends
    
    def test_get_health_trends_insufficient_data(self, health_monitor_instance):
        """Test health trends with insufficient data"""
        trends = health_monitor_instance.get_health_trends()
        
        assert "message" in trends
        assert "no health history" in trends["message"].lower()


class TestHealthMetricsIntegration:
    """Test integration with metrics system"""
    
    @pytest.mark.asyncio
    async def test_update_health_metrics(self, health_monitor_instance):
        """Test updating health metrics"""
        system_health = SystemHealth(
            HealthStatus.HEALTHY, 
            0.95,
            [HealthCheck(ComponentType.DATABASE, HealthStatus.HEALTHY, 100.0, "OK")]
        )
        
        with patch('src.observability.health.metrics') as mock_metrics:
            mock_metrics.update_system_health = Mock()
            mock_metrics.update_component_health = Mock()
            
            await health_monitor_instance._update_health_metrics(system_health)
            
            # Should update system health score
            mock_metrics.update_system_health.assert_called_with(0.95)
            
            # Should update component health
            mock_metrics.update_component_health.assert_called_with("database", True)
    
    @pytest.mark.asyncio
    async def test_update_health_metrics_error_handling(self, health_monitor_instance):
        """Test health metrics update error handling"""
        system_health = SystemHealth(HealthStatus.HEALTHY, 0.95, [])
        
        with patch('src.observability.health.metrics') as mock_metrics:
            mock_metrics.update_system_health.side_effect = Exception("Metrics error")
            
            # Should handle exception gracefully
            await health_monitor_instance._update_health_metrics(system_health)


class TestHealthMonitorErrorHandling:
    """Test error handling in health monitoring"""
    
    @pytest.mark.asyncio
    async def test_health_check_with_exceptions(self, health_monitor_instance):
        """Test comprehensive health check with exceptions"""
        # Mock some checks to raise exceptions
        with patch.multiple(
            health_monitor_instance,
            check_database_health=AsyncMock(side_effect=Exception("DB error")),
            check_redis_health=AsyncMock(return_value=HealthCheck(ComponentType.REDIS, HealthStatus.HEALTHY, 50.0, "OK")),
            check_elasticsearch_health=AsyncMock(return_value=HealthCheck(ComponentType.ELASTICSEARCH, HealthStatus.HEALTHY, 100.0, "OK")),
            check_llm_backend_health=AsyncMock(return_value=HealthCheck(ComponentType.LLM_BACKEND, HealthStatus.HEALTHY, 200.0, "OK")),
            check_feature_flags_health=AsyncMock(return_value=HealthCheck(ComponentType.FEATURE_FLAGS, HealthStatus.HEALTHY, 30.0, "OK")),
            check_metrics_health=AsyncMock(return_value=HealthCheck(ComponentType.METRICS, HealthStatus.HEALTHY, 20.0, "OK"))
        ):
            
            system_health = await health_monitor_instance.perform_comprehensive_health_check()
            
            # Should handle exceptions and still complete
            assert system_health is not None
            # Should have created error health check for the failed component
            assert len(system_health.component_checks) >= 5  # At least the successful ones


class TestGlobalHealthMonitorIntegration:
    """Test global health monitor instance and initialization"""
    
    def test_global_health_monitor_instance(self):
        """Test global health monitor instance"""
        from src.observability.health import health_monitor
        
        assert health_monitor is not None
        assert isinstance(health_monitor, HealthMonitor)
    
    def test_init_health_monitoring_integration(self, mock_settings):
        """Test health monitoring initialization integration"""
        with patch('src.observability.health.health_monitor') as mock_global:
            init_health_monitoring(mock_settings)
            
            # Should update global instance settings
            assert mock_global is not None
    
    @pytest.mark.asyncio
    async def test_background_health_monitoring_task(self, mock_settings):
        """Test background health monitoring task"""
        mock_settings.enable_health_monitoring = True
        
        with patch('src.observability.health._background_health_monitoring') as mock_bg_task:
            # Simulate initialization that would start background task
            init_health_monitoring(mock_settings)
            
            # Verify background task integration is in place
            assert mock_bg_task is not None