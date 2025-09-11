"""
Performance tests for observability systems.

Tests metrics collection, health monitoring, and medical metrics performance
to ensure minimal impact on system responsiveness.
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.config.enhanced_settings import EnhancedSettings
from src.observability.health import HealthMonitor
from src.observability.medical_metrics import MedicalMetricsCollector
from src.observability.metrics import MetricsCollector


@pytest.fixture
def performance_settings():
    """Settings optimized for performance testing"""
    return EnhancedSettings(
        environment="performance_test",
        features__enable_metrics=True,
        features__enable_medical_metrics=True,
        observability__health_check_interval=30,
        observability__log_query_metrics=False  # Disable verbose logging for performance
    )


@pytest.fixture
def metrics_collector(performance_settings):
    """Metrics collector for performance testing"""
    return MetricsCollector(performance_settings)


@pytest.fixture
def medical_metrics_collector(performance_settings):
    """Medical metrics collector for performance testing"""
    return MedicalMetricsCollector(performance_settings)


@pytest.fixture
def health_monitor(performance_settings):
    """Health monitor for performance testing"""
    return HealthMonitor(performance_settings)


@pytest.fixture
def mock_prometheus_metrics():
    """Mock Prometheus metrics for performance testing"""
    mocks = {}
    metric_names = [
        'query_total', 'query_duration', 'query_confidence',
        'medical_queries_by_specialty', 'clinical_confidence_distribution',
        'safety_alerts', 'system_health', 'component_health'
    ]
    
    for name in metric_names:
        mock_metric = Mock()
        mock_metric.labels.return_value.inc = Mock()
        mock_metric.labels.return_value.observe = Mock()
        mock_metric.labels.return_value.set = Mock()
        mock_metric.set = Mock()
        mocks[name] = mock_metric
    
    return mocks


class TestMetricsCollectionPerformance:
    """Test metrics collection performance impact"""
    
    def test_single_query_metrics_overhead(self, metrics_collector, mock_prometheus_metrics):
        """Test overhead of tracking a single query"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics):
            # Baseline measurement (no metrics)
            start_time = time.perf_counter()
            for _ in range(1000):
                pass  # Baseline loop
            baseline_time = time.perf_counter() - start_time
            
            # With metrics tracking
            start_time = time.perf_counter()
            for i in range(1000):
                metrics_collector.track_query(
                    query_type="PROTOCOL_STEPS",
                    duration=1.0 + (i % 10) * 0.1,
                    confidence=0.8 + (i % 20) * 0.01,
                    cache_hit=i % 3 == 0,
                    backend="hybrid"
                )
            metrics_time = time.perf_counter() - start_time
            
            # Calculate overhead
            overhead = metrics_time - baseline_time
            overhead_per_call = overhead / 1000
            
            print(f"Metrics overhead: {overhead:.4f}s total, {overhead_per_call*1000:.3f}ms per call")
            
            # Overhead should be minimal (< 1ms per call)
            assert overhead_per_call < 0.001, f"Metrics overhead too high: {overhead_per_call*1000:.3f}ms per call"
    
    def test_concurrent_metrics_collection(self, metrics_collector, mock_prometheus_metrics):
        """Test metrics collection under concurrent load"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics):
            
            def collect_metrics_batch(batch_size=100):
                """Collect a batch of metrics"""
                for i in range(batch_size):
                    metrics_collector.track_query("PROTOCOL_STEPS", 1.0, 0.8)
                    metrics_collector.track_cache_operation("get", "PROTOCOL_STEPS", True, 0.9)
                    metrics_collector.track_llm_request("ollama", 1.5, 100, 50)
            
            # Test concurrent metrics collection
            start_time = time.perf_counter()
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(collect_metrics_batch, 50)
                    for _ in range(8)  # 8 threads, 50 metrics each = 400 total
                ]
                
                # Wait for all threads to complete
                for future in futures:
                    future.result()
            
            total_time = time.perf_counter() - start_time
            metrics_per_second = 400 / total_time
            
            print(f"Concurrent metrics: {metrics_per_second:.0f} metrics/second")
            
            # Should handle at least 1000 metrics per second
            assert metrics_per_second > 1000, f"Metrics throughput too low: {metrics_per_second:.0f}/sec"
    
    def test_metrics_memory_usage(self, metrics_collector, mock_prometheus_metrics):
        """Test metrics collection memory efficiency"""
        import os

        import psutil
        
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics):
            process = psutil.Process(os.getpid())
            
            # Baseline memory
            baseline_memory = process.memory_info().rss
            
            # Collect many metrics
            for i in range(10000):
                metrics_collector.track_query("PROTOCOL_STEPS", 1.0, 0.8)
                if i % 100 == 0:
                    metrics_collector.track_hybrid_search(
                        "PROTOCOL_STEPS", 0.1, 0.3, 0.05,
                        {"keyword": 10, "semantic": 15}
                    )
            
            # Memory after metrics collection
            final_memory = process.memory_info().rss
            memory_increase = final_memory - baseline_memory
            
            print(f"Memory increase: {memory_increase / 1024 / 1024:.2f} MB for 10k metrics")
            
            # Memory increase should be reasonable (< 50MB for 10k metrics)
            assert memory_increase < 50 * 1024 * 1024, f"Memory usage too high: {memory_increase/1024/1024:.2f}MB"
    
    def test_disabled_metrics_performance(self, performance_settings, mock_prometheus_metrics):
        """Test performance when metrics are disabled"""
        # Create disabled metrics collector
        performance_settings.enable_metrics = False
        disabled_collector = MetricsCollector(performance_settings)
        
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics):
            start_time = time.perf_counter()
            
            # Track metrics (should be no-ops)
            for i in range(1000):
                disabled_collector.track_query("PROTOCOL_STEPS", 1.0, 0.8)
                disabled_collector.track_cache_operation("get", "PROTOCOL_STEPS", True)
                disabled_collector.track_llm_request("ollama", 1.5)
            
            disabled_time = time.perf_counter() - start_time
            
            print(f"Disabled metrics time: {disabled_time:.4f}s")
            
            # Disabled metrics should be extremely fast (< 10ms for 1000 calls)
            assert disabled_time < 0.01, f"Disabled metrics too slow: {disabled_time:.4f}s"
            
            # Verify no metrics were actually called
            for mock_metric in mock_prometheus_metrics.values():
                mock_metric.labels.assert_not_called()


class TestMedicalMetricsPerformance:
    """Test medical metrics performance"""
    
    def test_medical_specialty_classification_performance(self, medical_metrics_collector):
        """Test medical specialty classification performance"""
        queries = [
            "chest pain protocol STEMI activation",
            "morphine dosage for severe pain management",
            "cardiology on call contact information",
            "trauma team activation criteria",
            "insulin sliding scale protocol",
            "sepsis bundle implementation",
            "respiratory failure intubation protocol",
            "stroke alert procedure steps"
        ]
        
        start_time = time.perf_counter()
        
        # Classify many queries
        for _ in range(1000):
            for query in queries:
                specialty = medical_metrics_collector.classify_medical_specialty(query)
                assert specialty in ["cardiology", "emergency", "pharmacy", "pulmonology", "neurology", "general"]
        
        classification_time = time.perf_counter() - start_time
        classifications_per_second = (1000 * len(queries)) / classification_time
        
        print(f"Medical classification: {classifications_per_second:.0f} classifications/second")
        
        # Should handle at least 5000 classifications per second
        assert classifications_per_second > 5000, f"Classification too slow: {classifications_per_second:.0f}/sec"
    
    def test_medication_extraction_performance(self, medical_metrics_collector):
        """Test medication extraction performance"""
        queries = [
            "morphine 2mg IV push for pain",
            "insulin 10 units subcutaneous",
            "heparin bolus 5000 units",
            "aspirin 325mg by mouth",
            "tylenol 650mg PO",
            "albuterol nebulizer treatment",
            "lisinopril 10mg daily",
            "metoprolol 25mg twice daily"
        ]
        
        start_time = time.perf_counter()
        
        # Extract medications from many queries
        for _ in range(1000):
            for query in queries:
                medication = medical_metrics_collector.extract_medication(query)
                dosage_info = medical_metrics_collector.extract_dosage_info(query)
                assert isinstance(medication, str)
                assert isinstance(dosage_info, dict)
        
        extraction_time = time.perf_counter() - start_time
        extractions_per_second = (1000 * len(queries)) / extraction_time
        
        print(f"Medication extraction: {extractions_per_second:.0f} extractions/second")
        
        # Should handle at least 3000 extractions per second
        assert extractions_per_second > 3000, f"Extraction too slow: {extractions_per_second:.0f}/sec"
    
    def test_complete_medical_metrics_workflow(self, medical_metrics_collector, mock_prometheus_metrics):
        """Test complete medical metrics workflow performance"""
        with patch.multiple('src.observability.medical_metrics', **mock_prometheus_metrics):
            
            medical_queries = [
                ("STEMI protocol for chest pain", "PROTOCOL_STEPS", 0.92),
                ("morphine 2mg IV dosage", "DOSAGE_LOOKUP", 0.88),
                ("cardiology contact on call", "CONTACT_LOOKUP", 0.95),
                ("sepsis criteria checklist", "CRITERIA_CHECK", 0.89)
            ]
            
            start_time = time.perf_counter()
            
            # Process many medical queries
            for _ in range(500):
                for query, query_type, confidence in medical_queries:
                    medical_metrics_collector.track_medical_query(
                        query, query_type, confidence, 1.2
                    )
            
            workflow_time = time.perf_counter() - start_time
            workflows_per_second = (500 * len(medical_queries)) / workflow_time
            
            print(f"Medical workflow: {workflows_per_second:.0f} workflows/second")
            
            # Should handle at least 1000 workflows per second
            assert workflows_per_second > 1000, f"Medical workflow too slow: {workflows_per_second:.0f}/sec"


class TestHealthMonitoringPerformance:
    """Test health monitoring performance"""
    
    @pytest.mark.asyncio
    async def test_individual_health_check_performance(self, health_monitor):
        """Test individual health check performance"""
        # Mock database health check
        with patch('src.observability.health.get_database') as mock_db:
            mock_db_conn = AsyncMock()
            mock_result = Mock()
            mock_result.fetchone.return_value = [1]
            mock_db_conn.execute.return_value = mock_result
            mock_db.__aenter__.return_value = mock_db_conn
            mock_db.__aexit__.return_value = None
            
            # Time database health check
            start_time = time.perf_counter()
            
            for _ in range(10):  # Multiple checks
                check = await health_monitor.check_database_health()
                assert check.response_time_ms < 100  # Should be fast
            
            total_time = time.perf_counter() - start_time
            avg_time = total_time / 10
            
            print(f"Database health check: {avg_time*1000:.2f}ms average")
            
            # Each health check should be fast (< 50ms)
            assert avg_time < 0.05, f"Health check too slow: {avg_time*1000:.2f}ms"
    
    @pytest.mark.asyncio
    async def test_comprehensive_health_check_performance(self, health_monitor):
        """Test comprehensive health check performance"""
        with patch('src.observability.health.get_database') as mock_db, \
             patch('redis.asyncio.Redis') as mock_redis, \
             patch('aiohttp.ClientSession') as mock_session:
            
            # Mock all health checks to be fast
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
            
            mock_response = Mock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={'models': []})
            mock_http_session = AsyncMock()
            mock_http_session.get.return_value.__aenter__.return_value = mock_response
            mock_http_session.get.return_value.__aexit__.return_value = None
            mock_session.return_value = mock_http_session
            
            # Time comprehensive health check
            start_time = time.perf_counter()
            
            system_health = await health_monitor.perform_comprehensive_health_check()
            
            check_time = time.perf_counter() - start_time
            
            print(f"Comprehensive health check: {check_time*1000:.2f}ms")
            
            # Comprehensive check should complete quickly (< 500ms)
            assert check_time < 0.5, f"Comprehensive health check too slow: {check_time*1000:.2f}ms"
            assert system_health is not None
            assert len(system_health.component_checks) > 0
    
    @pytest.mark.asyncio
    async def test_health_monitoring_concurrency(self, health_monitor):
        """Test health monitoring under concurrent load"""
        with patch('src.observability.health.get_database') as mock_db:
            mock_db_conn = AsyncMock()
            mock_result = Mock()
            mock_result.fetchone.return_value = [1]
            mock_db_conn.execute.return_value = mock_result
            mock_db.__aenter__.return_value = mock_db_conn
            mock_db.__aexit__.return_value = None
            
            async def run_health_checks(count=10):
                """Run multiple health checks"""
                tasks = [
                    health_monitor.check_database_health()
                    for _ in range(count)
                ]
                return await asyncio.gather(*tasks)
            
            start_time = time.perf_counter()
            
            # Run concurrent health checks
            results = await run_health_checks(20)
            
            concurrent_time = time.perf_counter() - start_time
            
            print(f"20 concurrent health checks: {concurrent_time*1000:.2f}ms")
            
            # Concurrent checks should complete quickly due to async nature
            assert concurrent_time < 0.2, f"Concurrent health checks too slow: {concurrent_time*1000:.2f}ms"
            assert len(results) == 20
            assert all(check.component.value == "database" for check in results)


class TestConfigurationPerformance:
    """Test configuration system performance"""
    
    @pytest.mark.asyncio
    async def test_feature_flag_access_performance(self, mock_redis):
        """Test feature flag access performance"""
        from src.config.enhanced_settings import EnhancedSettings
        from src.config.feature_manager import FeatureManager
        
        settings = EnhancedSettings(
            environment="performance_test",
            features__enable_hybrid_search=False
        )
        
        with patch('src.config.feature_manager.get_redis_client', return_value=mock_redis):
            feature_manager = FeatureManager(settings)
            await feature_manager._ensure_redis_connection()
            
            # Mock Redis responses
            mock_redis.get.return_value = None  # No overrides
            
            start_time = time.perf_counter()
            
            # Access flags many times
            for _ in range(1000):
                flag_value = await feature_manager.get_flag("enable_hybrid_search")
                assert flag_value is False
            
            access_time = time.perf_counter() - start_time
            accesses_per_second = 1000 / access_time
            
            print(f"Feature flag access: {accesses_per_second:.0f} accesses/second")
            
            # Should handle at least 5000 accesses per second (with caching)
            assert accesses_per_second > 5000, f"Flag access too slow: {accesses_per_second:.0f}/sec"
    
    def test_settings_validation_performance(self):
        """Test settings validation performance"""
        from src.config.enhanced_settings import EnhancedSettings
        from src.config.validators import ConfigurationValidator
        
        settings = EnhancedSettings(
            environment="performance_test",
            features__enable_hybrid_search=True,
            features__enable_elasticsearch=True,
            features__search_backend="hybrid"
        )
        
        start_time = time.perf_counter()
        
        # Run validation many times
        for _ in range(100):
            validator = ConfigurationValidator(settings)
            warnings = validator.validate_all()
            assert isinstance(warnings, list)
        
        validation_time = time.perf_counter() - start_time
        validations_per_second = 100 / validation_time
        
        print(f"Configuration validation: {validations_per_second:.0f} validations/second")
        
        # Should handle at least 50 validations per second
        assert validations_per_second > 50, f"Validation too slow: {validations_per_second:.0f}/sec"


class TestIntegratedSystemPerformance:
    """Test performance of integrated observability system"""
    
    def test_complete_query_processing_performance(self, mock_prometheus_metrics):
        """Test performance impact of complete observability on query processing"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics), \
             patch.multiple('src.observability.medical_metrics', **mock_prometheus_metrics):
            
            from src.observability.medical_metrics import medical_metrics
            from src.observability.metrics import metrics
            
            metrics.enabled = True
            medical_metrics.enabled = True
            
            def simulate_query_processing():
                """Simulate complete query processing with observability"""
                # Core metrics
                metrics.track_query("PROTOCOL_STEPS", 1.2, 0.88, True, "hybrid")
                metrics.track_cache_operation("get", "PROTOCOL_STEPS", True, 0.92)
                metrics.track_hybrid_search(
                    "PROTOCOL_STEPS", 0.1, 0.3, 0.05,
                    {"keyword": 10, "semantic": 15}
                )
                metrics.track_llm_request("ollama", 1.5, 150, 75)
                
                # Medical metrics
                medical_metrics.track_medical_query(
                    "chest pain protocol STEMI",
                    "PROTOCOL_STEPS", 0.88, 1.2
                )
                
                # Safety tracking
                metrics.track_safety_alert("low_confidence", "warning")
                
                return True
            
            # Baseline without observability
            start_time = time.perf_counter()
            for _ in range(1000):
                pass  # Baseline
            baseline_time = time.perf_counter() - start_time
            
            # With full observability
            start_time = time.perf_counter()
            for _ in range(1000):
                result = simulate_query_processing()
                assert result is True
            observability_time = time.perf_counter() - start_time
            
            # Calculate overhead
            overhead = observability_time - baseline_time
            overhead_percentage = (overhead / observability_time) * 100
            
            print(f"Complete observability overhead: {overhead:.4f}s ({overhead_percentage:.1f}%)")
            
            # Total observability overhead should be reasonable (< 20% for this synthetic test)
            assert overhead_percentage < 20, f"Observability overhead too high: {overhead_percentage:.1f}%"
    
    @pytest.mark.asyncio
    async def test_system_under_load_performance(self, mock_prometheus_metrics):
        """Test system performance under sustained load"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics), \
             patch.multiple('src.observability.medical_metrics', **mock_prometheus_metrics):
            
            from src.observability.health import HealthMonitor
            from src.observability.medical_metrics import medical_metrics
            from src.observability.metrics import metrics
            
            metrics.enabled = True
            medical_metrics.enabled = True
            
            # Mock health monitor
            with patch('src.observability.health.get_database') as mock_db:
                mock_db_conn = AsyncMock()
                mock_result = Mock()
                mock_result.fetchone.return_value = [1]
                mock_db_conn.execute.return_value = mock_result
                mock_db.__aenter__.return_value = mock_db_conn
                mock_db.__aexit__.return_value = None
                
                health_monitor = HealthMonitor()
                
                async def sustained_load():
                    """Simulate sustained system load"""
                    tasks = []
                    
                    # Metrics collection load
                    for i in range(50):
                        metrics.track_query(f"PROTOCOL_{i%5}", 1.0, 0.8)
                        medical_metrics.track_medical_query(
                            f"test query {i}", "PROTOCOL_STEPS", 0.8, 1.0
                        )
                    
                    # Health monitoring load
                    for _ in range(5):
                        task = asyncio.create_task(health_monitor.check_database_health())
                        tasks.append(task)
                    
                    # Wait for health checks
                    await asyncio.gather(*tasks)
                    
                    return len(tasks)
                
                start_time = time.perf_counter()
                
                # Run sustained load test
                result = await sustained_load()
                
                load_time = time.perf_counter() - start_time
                
                print(f"Sustained load test: {load_time*1000:.2f}ms for 50 metrics + 5 health checks")
                
                # Should handle sustained load efficiently (< 100ms)
                assert load_time < 0.1, f"Sustained load performance poor: {load_time*1000:.2f}ms"
                assert result == 5  # All health checks completed


class TestPerformanceRegression:
    """Test for performance regressions"""
    
    def test_performance_baseline_metrics(self, mock_prometheus_metrics):
        """Establish performance baselines for regression testing"""
        with patch.multiple('src.observability.metrics', **mock_prometheus_metrics):
            from src.observability.metrics import MetricsCollector
            
            collector = MetricsCollector()
            collector.enabled = True
            
            # Define performance targets
            targets = {
                "single_metric_call": 0.001,  # < 1ms per metric call
                "batch_metrics_1000": 0.1,    # < 100ms for 1000 metrics
                "concurrent_metrics": 1000    # > 1000 metrics/second
            }
            
            # Test single metric call
            start_time = time.perf_counter()
            collector.track_query("PROTOCOL_STEPS", 1.0, 0.8)
            single_call_time = time.perf_counter() - start_time
            
            # Test batch metrics
            start_time = time.perf_counter()
            for i in range(1000):
                collector.track_query("PROTOCOL_STEPS", 1.0, 0.8)
            batch_time = time.perf_counter() - start_time
            
            # Test concurrent throughput
            start_time = time.perf_counter()
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(lambda: [collector.track_query("PROTOCOL_STEPS", 1.0, 0.8) for _ in range(500)])
                    for _ in range(2)
                ]
                for future in futures:
                    future.result()
            concurrent_time = time.perf_counter() - start_time
            concurrent_throughput = 1000 / concurrent_time
            
            # Verify against targets
            results = {
                "single_metric_call": single_call_time,
                "batch_metrics_1000": batch_time,
                "concurrent_metrics": concurrent_throughput
            }
            
            print("Performance baseline results:")
            for metric, result in results.items():
                if metric == "concurrent_metrics":
                    print(f"  {metric}: {result:.0f} metrics/sec (target: >{targets[metric]})")
                    assert result > targets[metric], f"Performance regression: {metric}"
                else:
                    print(f"  {metric}: {result*1000:.2f}ms (target: <{targets[metric]*1000}ms)")
                    assert result < targets[metric], f"Performance regression: {metric}"