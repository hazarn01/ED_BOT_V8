"""
Unit tests for metrics collection framework.
"""

import time
from unittest.mock import Mock, patch

import pytest

from src.observability.metrics import (
    MetricsCollector,
    init_metrics,
    track_concurrent_request,
    track_elasticsearch_metrics,
    track_llm_metrics,
    track_query_metrics,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for metrics testing"""
    settings = Mock()
    settings.enable_metrics = True
    settings.enable_medical_metrics = True
    return settings


@pytest.fixture
def metrics_collector(mock_settings):
    """Create metrics collector instance"""
    return MetricsCollector(mock_settings)


@pytest.fixture
def disabled_metrics_collector():
    """Create disabled metrics collector"""
    settings = Mock()
    settings.enable_metrics = False
    return MetricsCollector(settings)


class TestMetricsCollectorInitialization:
    """Test metrics collector initialization"""
    
    def test_metrics_collector_init_enabled(self, mock_settings):
        """Test metrics collector initialization with enabled metrics"""
        collector = MetricsCollector(mock_settings)
        
        assert collector.settings is mock_settings
        assert collector.enabled is True
    
    def test_metrics_collector_init_disabled(self):
        """Test metrics collector initialization with disabled metrics"""
        settings = Mock()
        settings.enable_metrics = False
        
        collector = MetricsCollector(settings)
        
        assert collector.enabled is False
    
    def test_metrics_collector_init_no_settings(self):
        """Test metrics collector initialization without settings"""
        collector = MetricsCollector()
        
        assert collector.settings is None
        assert collector.enabled is True  # Default enabled
    
    def test_init_metrics_function(self, mock_settings):
        """Test init_metrics function"""
        with patch('src.observability.metrics.metrics') as mock_metrics_instance:
            init_metrics(mock_settings)
            
            assert mock_metrics_instance.settings is mock_settings
            assert mock_metrics_instance.enabled is True


class TestQueryMetricsTracking:
    """Test query metrics tracking"""
    
    def test_track_query_enabled(self, metrics_collector):
        """Test query tracking when metrics enabled"""
        with patch('src.observability.metrics.query_total') as mock_counter, \
             patch('src.observability.metrics.query_duration') as mock_histogram, \
             patch('src.observability.metrics.query_confidence') as mock_confidence:
            
            mock_counter.labels.return_value.inc = Mock()
            mock_histogram.labels.return_value.observe = Mock()
            mock_confidence.labels.return_value.observe = Mock()
            
            metrics_collector.track_query(
                query_type="PROTOCOL_STEPS",
                duration=1.5,
                confidence=0.85,
                cache_hit=True,
                backend="hybrid"
            )
            
            # Verify counter increment
            mock_counter.labels.assert_called_with(
                query_type="PROTOCOL_STEPS",
                status="success",
                cache_hit="hit"
            )
            mock_counter.labels.return_value.inc.assert_called_once()
            
            # Verify duration observation
            mock_histogram.labels.assert_called_with(
                query_type="PROTOCOL_STEPS",
                backend="hybrid"
            )
            mock_histogram.labels.return_value.observe.assert_called_with(1.5)
            
            # Verify confidence observation
            mock_confidence.labels.assert_called_with(query_type="PROTOCOL_STEPS")
            mock_confidence.labels.return_value.observe.assert_called_with(0.85)
    
    def test_track_query_disabled(self, disabled_metrics_collector):
        """Test query tracking when metrics disabled"""
        with patch('src.observability.metrics.query_total') as mock_counter:
            mock_counter.labels.return_value.inc = Mock()
            
            disabled_metrics_collector.track_query(
                query_type="PROTOCOL_STEPS",
                duration=1.5,
                confidence=0.85
            )
            
            # Should not call metrics
            mock_counter.labels.assert_not_called()
    
    def test_track_query_cache_miss(self, metrics_collector):
        """Test query tracking with cache miss"""
        with patch('src.observability.metrics.query_total') as mock_counter:
            mock_counter.labels.return_value.inc = Mock()
            
            metrics_collector.track_query(
                query_type="DOSAGE_LOOKUP",
                duration=0.8,
                confidence=0.92,
                cache_hit=False
            )
            
            mock_counter.labels.assert_called_with(
                query_type="DOSAGE_LOOKUP",
                status="success",
                cache_hit="miss"
            )


class TestHybridSearchMetricsTracking:
    """Test hybrid search metrics tracking"""
    
    def test_track_hybrid_search(self, metrics_collector):
        """Test hybrid search metrics tracking"""
        with patch('src.observability.metrics.hybrid_retrieval_duration') as mock_duration, \
             patch('src.observability.metrics.hybrid_result_sources') as mock_sources:
            
            mock_duration.labels.return_value.observe = Mock()
            mock_sources.labels.return_value.inc = Mock()
            
            metrics_collector.track_hybrid_search(
                query_type="PROTOCOL_STEPS",
                keyword_time=0.1,
                semantic_time=0.3,
                fusion_time=0.05,
                result_sources={"keyword": 10, "semantic": 15, "both": 5}
            )
            
            # Verify component timing observations
            expected_calls = [
                (("keyword",), 0.1),
                (("semantic",), 0.3),
                (("fusion",), 0.05)
            ]
            
            for (component,), duration in expected_calls:
                mock_duration.labels.assert_any_call(component=component)
                mock_duration.labels.return_value.observe.assert_any_call(duration)
            
            # Verify result source tracking
            expected_source_calls = [
                (("PROTOCOL_STEPS", "keyword"), 10),
                (("PROTOCOL_STEPS", "semantic"), 15),
                (("PROTOCOL_STEPS", "both"), 5)
            ]
            
            for (query_type, source), count in expected_source_calls:
                mock_sources.labels.assert_any_call(
                    query_type=query_type,
                    source=source
                )
                mock_sources.labels.return_value.inc.assert_any_call(count)


class TestCacheMetricsTracking:
    """Test cache metrics tracking"""
    
    def test_track_cache_operation_hit(self, metrics_collector):
        """Test cache hit tracking"""
        with patch('src.observability.metrics.cache_operations') as mock_operations, \
             patch('src.observability.metrics.cache_similarity_scores') as mock_similarity:
            
            mock_operations.labels.return_value.inc = Mock()
            mock_similarity.labels.return_value.observe = Mock()
            
            metrics_collector.track_cache_operation(
                operation="get",
                query_type="PROTOCOL_STEPS",
                hit=True,
                similarity=0.95
            )
            
            # Verify cache operation tracking
            mock_operations.labels.assert_called_with(
                operation="get",
                query_type="PROTOCOL_STEPS",
                result="hit"
            )
            mock_operations.labels.return_value.inc.assert_called_once()
            
            # Verify similarity score tracking
            mock_similarity.labels.assert_called_with(query_type="PROTOCOL_STEPS")
            mock_similarity.labels.return_value.observe.assert_called_with(0.95)
    
    def test_track_cache_operation_miss(self, metrics_collector):
        """Test cache miss tracking"""
        with patch('src.observability.metrics.cache_operations') as mock_operations:
            mock_operations.labels.return_value.inc = Mock()
            
            metrics_collector.track_cache_operation(
                operation="get",
                query_type="DOSAGE_LOOKUP",
                hit=False
            )
            
            mock_operations.labels.assert_called_with(
                operation="get",
                query_type="DOSAGE_LOOKUP",
                result="miss"
            )
    
    def test_track_cache_operation_set(self, metrics_collector):
        """Test cache set operation tracking"""
        with patch('src.observability.metrics.cache_operations') as mock_operations:
            mock_operations.labels.return_value.inc = Mock()
            
            metrics_collector.track_cache_operation(
                operation="set",
                query_type="CRITERIA_CHECK"
            )
            
            mock_operations.labels.assert_called_with(
                operation="set",
                query_type="CRITERIA_CHECK",
                result="set"
            )


class TestTableExtractionMetricsTracking:
    """Test table extraction metrics tracking"""
    
    def test_track_table_extraction_high_confidence(self, metrics_collector):
        """Test table extraction tracking with high confidence"""
        with patch('src.observability.metrics.table_extraction_duration') as mock_duration, \
             patch('src.observability.metrics.tables_extracted') as mock_count:
            
            mock_duration.labels.return_value.observe = Mock()
            mock_count.labels.return_value.inc = Mock()
            
            metrics_collector.track_table_extraction(
                method="unstructured",
                duration=5.2,
                table_count=3,
                table_type="dosing",
                confidence=0.85
            )
            
            # Verify duration tracking
            mock_duration.labels.assert_called_with(extraction_method="unstructured")
            mock_duration.labels.return_value.observe.assert_called_with(5.2)
            
            # Verify count tracking with high confidence bucket
            mock_count.labels.assert_called_with(
                table_type="dosing",
                confidence_bucket="high"
            )
            mock_count.labels.return_value.inc.assert_called_with(3)
    
    def test_track_table_extraction_confidence_buckets(self, metrics_collector):
        """Test table extraction confidence bucket classification"""
        with patch('src.observability.metrics.tables_extracted') as mock_count:
            mock_count.labels.return_value.inc = Mock()
            
            # Test different confidence levels
            test_cases = [
                (0.9, "high"),
                (0.75, "medium"),
                (0.5, "low")
            ]
            
            for confidence, expected_bucket in test_cases:
                metrics_collector.track_table_extraction(
                    method="test",
                    duration=1.0,
                    table_count=1,
                    confidence=confidence
                )
                
                mock_count.labels.assert_any_call(
                    table_type="unknown",
                    confidence_bucket=expected_bucket
                )


class TestSafetyMetricsTracking:
    """Test safety metrics tracking"""
    
    def test_track_safety_alert(self, metrics_collector):
        """Test safety alert tracking"""
        with patch('src.observability.metrics.safety_alerts') as mock_alerts, \
             patch('src.observability.metrics.logger') as mock_logger:
            
            mock_alerts.labels.return_value.inc = Mock()
            
            metrics_collector.track_safety_alert(
                alert_type="low_confidence",
                severity="warning"
            )
            
            # Verify alert tracking
            mock_alerts.labels.assert_called_with(
                alert_type="low_confidence",
                severity="warning"
            )
            mock_alerts.labels.return_value.inc.assert_called_once()
            
            # Verify logging
            mock_logger.warning.assert_called_once()
    
    def test_track_phi_scrubbing(self, metrics_collector):
        """Test PHI scrubbing event tracking"""
        with patch('src.observability.metrics.phi_scrubbing_events') as mock_phi:
            mock_phi.labels.return_value.inc = Mock()
            
            metrics_collector.track_phi_scrubbing(
                component="query",
                event_count=2
            )
            
            mock_phi.labels.assert_called_with(component="query")
            mock_phi.labels.return_value.inc.assert_called_with(2)


class TestLLMMetricsTracking:
    """Test LLM metrics tracking"""
    
    def test_track_llm_request_success(self, metrics_collector):
        """Test successful LLM request tracking"""
        with patch('src.observability.metrics.llm_backend_requests') as mock_requests, \
             patch('src.observability.metrics.llm_backend_duration') as mock_duration, \
             patch('src.observability.metrics.llm_tokens') as mock_tokens:
            
            mock_requests.labels.return_value.inc = Mock()
            mock_duration.labels.return_value.observe = Mock()
            mock_tokens.labels.return_value.inc = Mock()
            
            metrics_collector.track_llm_request(
                backend="ollama",
                duration=2.3,
                input_tokens=150,
                output_tokens=75,
                status="success"
            )
            
            # Verify request tracking
            mock_requests.labels.assert_called_with(
                backend="ollama",
                status="success"
            )
            mock_requests.labels.return_value.inc.assert_called_once()
            
            # Verify duration tracking
            mock_duration.labels.assert_called_with(backend="ollama")
            mock_duration.labels.return_value.observe.assert_called_with(2.3)
            
            # Verify token tracking
            mock_tokens.labels.assert_any_call(backend="ollama", type="input")
            mock_tokens.labels.assert_any_call(backend="ollama", type="output")
            mock_tokens.labels.return_value.inc.assert_any_call(150)
            mock_tokens.labels.return_value.inc.assert_any_call(75)
    
    def test_track_llm_request_no_tokens(self, metrics_collector):
        """Test LLM request tracking without token information"""
        with patch('src.observability.metrics.llm_tokens') as mock_tokens:
            mock_tokens.labels.return_value.inc = Mock()
            
            metrics_collector.track_llm_request(
                backend="ollama",
                duration=1.0
            )
            
            # Should not track tokens when not provided
            mock_tokens.labels.assert_not_called()


class TestSystemHealthMetricsTracking:
    """Test system health metrics tracking"""
    
    def test_update_system_health(self, metrics_collector):
        """Test system health score updates"""
        with patch('src.observability.metrics.system_health') as mock_health:
            mock_health.set = Mock()
            
            metrics_collector.update_system_health(0.85)
            
            mock_health.set.assert_called_with(0.85)
    
    def test_update_component_health(self, metrics_collector):
        """Test component health updates"""
        with patch('src.observability.metrics.component_health') as mock_component:
            mock_component.labels.return_value.set = Mock()
            
            metrics_collector.update_component_health("database", True)
            
            mock_component.labels.assert_called_with(component="database")
            mock_component.labels.return_value.set.assert_called_with(1.0)
            
            # Test unhealthy component
            metrics_collector.update_component_health("redis", False)
            
            mock_component.labels.assert_called_with(component="redis")
            mock_component.labels.return_value.set.assert_called_with(0.0)


class TestMetricsContextManagers:
    """Test metrics context managers and decorators"""
    
    def test_time_operation_context_manager(self, metrics_collector):
        """Test time_operation context manager"""
        mock_histogram = Mock()
        mock_histogram.labels.return_value.observe = Mock()
        
        labels = {"operation": "test"}
        
        with metrics_collector.time_operation(mock_histogram, labels):
            time.sleep(0.01)  # Small delay
        
        # Verify observation was made
        mock_histogram.labels.assert_called_with(**labels)
        mock_histogram.labels.return_value.observe.assert_called_once()
        
        # Verify duration is reasonable (should be >= 0.01)
        observed_duration = mock_histogram.labels.return_value.observe.call_args[0][0]
        assert observed_duration >= 0.01
    
    def test_time_operation_disabled(self, disabled_metrics_collector):
        """Test time_operation when metrics disabled"""
        mock_histogram = Mock()
        mock_histogram.labels.return_value.observe = Mock()
        
        with disabled_metrics_collector.time_operation(mock_histogram, {}):
            time.sleep(0.01)
        
        # Should not call histogram when disabled
        mock_histogram.labels.assert_not_called()
    
    def test_track_concurrent_request_context(self):
        """Test concurrent request tracking context manager"""
        with patch('src.observability.metrics.concurrent_requests') as mock_concurrent:
            mock_concurrent.inc = Mock()
            mock_concurrent.dec = Mock()
            
            with track_concurrent_request():
                # Inside context - should increment
                mock_concurrent.inc.assert_called_once()
                mock_concurrent.dec.assert_not_called()
            
            # After context - should decrement
            mock_concurrent.dec.assert_called_once()
    
    def test_track_concurrent_request_context_with_exception(self):
        """Test concurrent request context with exception"""
        with patch('src.observability.metrics.concurrent_requests') as mock_concurrent:
            mock_concurrent.inc = Mock()
            mock_concurrent.dec = Mock()
            
            try:
                with track_concurrent_request():
                    raise Exception("Test exception")
            except Exception:
                pass
            
            # Should still decrement even with exception
            mock_concurrent.inc.assert_called_once()
            mock_concurrent.dec.assert_called_once()


class TestMetricsDecorators:
    """Test metrics decorators"""
    
    @pytest.mark.asyncio
    async def test_track_query_metrics_decorator(self):
        """Test query metrics tracking decorator"""
        with patch('src.observability.metrics.metrics') as mock_metrics_instance:
            mock_metrics_instance.track_query = Mock()
            
            @track_query_metrics
            async def sample_function():
                # Mock result with metrics attributes
                result = Mock()
                result.query_type = "PROTOCOL_STEPS"
                result.confidence = 0.9
                result.cache_hit = True
                return result
            
            await sample_function()
            
            # Should track query metrics
            mock_metrics_instance.track_query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_track_elasticsearch_metrics_decorator(self):
        """Test Elasticsearch metrics tracking decorator"""
        with patch('src.observability.metrics.metrics') as mock_metrics_instance:
            mock_metrics_instance.track_elasticsearch_operation = Mock()
            
            @track_elasticsearch_metrics("search")
            async def sample_elasticsearch_function():
                return {"hits": {"total": 5}}
            
            await sample_elasticsearch_function()
            
            # Should track elasticsearch operation
            mock_metrics_instance.track_elasticsearch_operation.assert_called_once()
            args = mock_metrics_instance.track_elasticsearch_operation.call_args[0]
            assert args[0] == "search"  # operation
            assert args[2] == "success"  # status
    
    @pytest.mark.asyncio
    async def test_track_llm_metrics_decorator(self):
        """Test LLM metrics tracking decorator"""
        with patch('src.observability.metrics.metrics') as mock_metrics_instance:
            mock_metrics_instance.track_llm_request = Mock()
            
            @track_llm_metrics("ollama")
            async def sample_llm_function():
                result = Mock()
                result.input_tokens = 100
                result.output_tokens = 50
                return result
            
            await sample_llm_function()
            
            # Should track LLM request
            mock_metrics_instance.track_llm_request.assert_called_once()
            args = mock_metrics_instance.track_llm_request.call_args
            assert args[1]["backend"] == "ollama"
            assert args[1]["status"] == "success"


class TestMetricsErrorHandling:
    """Test metrics error handling"""
    
    def test_metrics_with_exception_in_tracking(self, metrics_collector):
        """Test graceful handling of exceptions in metrics tracking"""
        with patch('src.observability.metrics.query_total') as mock_counter:
            mock_counter.labels.side_effect = Exception("Prometheus error")
            
            # Should not raise exception
            metrics_collector.track_query(
                query_type="PROTOCOL_STEPS",
                duration=1.0,
                confidence=0.8
            )
    
    def test_time_operation_with_exception(self, metrics_collector):
        """Test time_operation context manager with exception"""
        mock_histogram = Mock()
        mock_histogram.labels.return_value.observe = Mock()
        
        try:
            with metrics_collector.time_operation(mock_histogram, {"test": "value"}):
                raise Exception("Test exception")
        except Exception:
            pass
        
        # Should still record timing even with exception
        mock_histogram.labels.return_value.observe.assert_called_once()


class TestMetricsIntegration:
    """Integration tests for metrics system"""
    
    def test_complete_query_workflow_metrics(self, metrics_collector):
        """Test metrics for complete query workflow"""
        with patch.multiple(
            'src.observability.metrics',
            query_total=Mock(),
            query_duration=Mock(),
            query_confidence=Mock(),
            cache_operations=Mock(),
            safety_alerts=Mock()
        ) as mocks:
            
            # Configure mocks
            for mock_metric in mocks.values():
                mock_metric.labels.return_value.inc = Mock()
                mock_metric.labels.return_value.observe = Mock()
            
            # Simulate complete workflow
            metrics_collector.track_query("PROTOCOL_STEPS", 1.2, 0.88, True)
            metrics_collector.track_cache_operation("get", "PROTOCOL_STEPS", True, 0.92)
            metrics_collector.track_safety_alert("low_confidence", "warning")
            
            # Verify all metrics were called
            mocks['query_total'].labels.assert_called()
            mocks['query_duration'].labels.assert_called()
            mocks['query_confidence'].labels.assert_called()
            mocks['cache_operations'].labels.assert_called()
            mocks['safety_alerts'].labels.assert_called()
    
    def test_metrics_initialization_integration(self, mock_settings):
        """Test complete metrics initialization"""
        with patch('src.observability.metrics.metrics') as mock_global_metrics:
            init_metrics(mock_settings)
            
            assert mock_global_metrics.settings is mock_settings
            assert mock_global_metrics.enabled is True
            
            # Test component health initialization
            expected_components = ['database', 'redis', 'elasticsearch', 'llm']
            
            # Should initialize component health for all components
            assert mock_global_metrics.update_component_health.call_count == len(expected_components)