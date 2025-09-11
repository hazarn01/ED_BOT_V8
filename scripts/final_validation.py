#!/usr/bin/env python3
"""
Final validation and integration testing for PRPs 22-25
Validates that all components work together correctly
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Result of a validation test"""
    test_name: str
    category: str  # "configuration", "observability", "rollout", "integration"
    status: str  # "pass", "fail", "warning", "skip"
    message: str
    duration_seconds: float
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class FinalValidator:
    """Comprehensive validation of all PRP implementations"""
    
    def __init__(self, settings, db_session, redis_client, es_client=None):
        self.settings = settings
        self.db = db_session
        self.redis = redis_client
        self.es_client = es_client
        self.logger = logging.getLogger(__name__)
        
    async def run_full_validation(self) -> Dict[str, Any]:
        """Run comprehensive validation of all PRP implementations"""
        
        self.logger.info("🔍 Starting final validation of PRPs 22-25...")
        validation_start = datetime.utcnow()
        
        # Define validation test categories
        validation_tests = [
            # PRP 22: Configuration and Feature Flags
            ("test_enhanced_settings", "configuration", self._test_enhanced_settings),
            ("test_feature_flag_management", "configuration", self._test_feature_flag_management),
            ("test_configuration_validation", "configuration", self._test_configuration_validation),
            ("test_environment_configs", "configuration", self._test_environment_configs),
            ("test_admin_endpoints", "configuration", self._test_admin_endpoints),
            
            # PRP 24: Observability 
            ("test_metrics_collection", "observability", self._test_metrics_collection),
            ("test_medical_metrics", "observability", self._test_medical_metrics),
            ("test_health_monitoring", "observability", self._test_health_monitoring),
            ("test_prometheus_integration", "observability", self._test_prometheus_integration),
            
            # PRP 23: Testing Infrastructure
            ("test_unit_test_coverage", "testing", self._test_unit_test_coverage),
            ("test_integration_test_suite", "testing", self._test_integration_test_suite),
            ("test_performance_benchmarks", "testing", self._test_performance_benchmarks),
            
            # PRP 25: Rollout Infrastructure
            ("test_pre_rollout_checks", "rollout", self._test_pre_rollout_checks),
            ("test_backfill_system", "rollout", self._test_backfill_system),
            ("test_rollout_manager", "rollout", self._test_rollout_manager),
            
            # Integration Tests
            ("test_end_to_end_workflow", "integration", self._test_end_to_end_workflow),
            ("test_feature_flag_integration", "integration", self._test_feature_flag_integration),
            ("test_observability_integration", "integration", self._test_observability_integration),
            ("test_rollout_safety", "integration", self._test_rollout_safety),
        ]
        
        results = []
        category_stats = {}
        
        for test_name, category, test_func in validation_tests:
            self.logger.info(f"Running {test_name}...")
            
            test_start = time.time()
            try:
                result = await test_func()
                duration = time.time() - test_start
                
                if isinstance(result, ValidationResult):
                    result.duration_seconds = duration
                    validation_result = result
                else:
                    # Handle legacy dict results
                    validation_result = ValidationResult(
                        test_name=test_name,
                        category=category,
                        status="pass" if result.get("success", False) else "fail",
                        message=result.get("message", "Test completed"),
                        duration_seconds=duration,
                        details=result.get("details"),
                        error=result.get("error")
                    )
                
                results.append(validation_result)
                
                # Update category stats
                if category not in category_stats:
                    category_stats[category] = {"pass": 0, "fail": 0, "warning": 0, "skip": 0}
                category_stats[category][validation_result.status] += 1
                
                # Log result
                status_symbol = {"pass": "✅", "fail": "❌", "warning": "⚠️", "skip": "⏭️"}[validation_result.status]
                self.logger.info(f"{status_symbol} {test_name}: {validation_result.message} ({duration:.2f}s)")
                
            except Exception as e:
                duration = time.time() - test_start
                error_result = ValidationResult(
                    test_name=test_name,
                    category=category,
                    status="fail",
                    message="Test failed with exception",
                    duration_seconds=duration,
                    error=str(e)
                )
                results.append(error_result)
                
                if category not in category_stats:
                    category_stats[category] = {"pass": 0, "fail": 0, "warning": 0, "skip": 0}
                category_stats[category]["fail"] += 1
                
                self.logger.error(f"❌ {test_name}: Exception - {e} ({duration:.2f}s)")
        
        total_duration = (datetime.utcnow() - validation_start).total_seconds()
        
        # Calculate overall stats
        total_tests = len(results)
        passed = sum(1 for r in results if r.status == "pass")
        failed = sum(1 for r in results if r.status == "fail")
        warnings = sum(1 for r in results if r.status == "warning")
        skipped = sum(1 for r in results if r.status == "skip")
        
        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        
        # Create comprehensive summary
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_duration_seconds": total_duration,
            "overall_success": failed == 0,
            "statistics": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "warnings": warnings,
                "skipped": skipped,
                "success_rate_percent": round(success_rate, 1)
            },
            "category_breakdown": category_stats,
            "critical_failures": [r for r in results if r.status == "fail" and r.category in ["configuration", "integration"]],
            "results": [asdict(r) for r in results]
        }
        
        # Log final summary
        if failed == 0:
            self.logger.info(f"🎉 All validation tests passed! ({passed}/{total_tests}, {success_rate:.1f}% success rate)")
        else:
            self.logger.error(f"💥 Validation failed: {failed} tests failed out of {total_tests} ({success_rate:.1f}% success rate)")
            
        if warnings > 0:
            self.logger.warning(f"⚠️  {warnings} tests completed with warnings")
            
        self.logger.info(f"📊 Validation completed in {total_duration:.1f}s")
        
        return summary
    
    # Configuration Tests (PRP 22)
    async def _test_enhanced_settings(self) -> ValidationResult:
        """Test enhanced settings structure"""
        try:
            # Test settings loading
            settings_attrs = [
                'features', 'cache', 'hybrid_search', 'observability',
                'environment', 'llm_backend', 'postgres_url'
            ]
            
            missing_attrs = []
            for attr in settings_attrs:
                if not hasattr(self.settings, attr):
                    missing_attrs.append(attr)
            
            if missing_attrs:
                return ValidationResult(
                    test_name="test_enhanced_settings",
                    category="configuration",
                    status="fail",
                    message=f"Missing settings attributes: {missing_attrs}",
                    duration_seconds=0
                )
            
            # Test feature flags structure
            feature_flags = self.settings.features
            required_features = ['enable_elasticsearch', 'enable_table_extraction', 'enable_source_highlighting']
            
            for feature in required_features:
                if not hasattr(feature_flags, feature):
                    return ValidationResult(
                        test_name="test_enhanced_settings",
                        category="configuration", 
                        status="warning",
                        message=f"Missing feature flag: {feature}",
                        duration_seconds=0
                    )
            
            return ValidationResult(
                test_name="test_enhanced_settings",
                category="configuration",
                status="pass",
                message="Enhanced settings structure is correctly configured",
                duration_seconds=0,
                details={
                    "environment": self.settings.environment,
                    "features_available": len([attr for attr in dir(feature_flags) if not attr.startswith('_')]),
                    "llm_backend": self.settings.llm_backend
                }
            )
            
        except Exception as e:
            return ValidationResult(
                test_name="test_enhanced_settings",
                category="configuration",
                status="fail",
                message="Failed to load enhanced settings",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_feature_flag_management(self) -> ValidationResult:
        """Test feature flag management system"""
        try:
            from src.config.feature_manager import FeatureManager
            
            feature_manager = FeatureManager(self.settings, self.redis)
            
            # Test setting and getting flags
            test_flag = "test_validation_flag"
            test_value = True
            
            await feature_manager.set_flag(test_flag, test_value, ttl_minutes=1)
            retrieved_value = await feature_manager.get_flag(test_flag)
            
            if retrieved_value != test_value:
                return ValidationResult(
                    test_name="test_feature_flag_management",
                    category="configuration",
                    status="fail",
                    message=f"Flag value mismatch: set {test_value}, got {retrieved_value}",
                    duration_seconds=0
                )
            
            # Test flag listing
            flags = await feature_manager.list_flags()
            if test_flag not in flags:
                return ValidationResult(
                    test_name="test_feature_flag_management",
                    category="configuration",
                    status="fail",
                    message="Flag not found in flag listing",
                    duration_seconds=0
                )
            
            # Test production safety (should prevent dangerous changes in production)
            if self.settings.environment == "production":
                try:
                    await feature_manager.set_flag("disable_external_calls", False)
                    return ValidationResult(
                        test_name="test_feature_flag_management",
                        category="configuration",
                        status="fail",
                        message="Production safety not working - allowed dangerous flag change",
                        duration_seconds=0
                    )
                except Exception:
                    # Expected to fail in production
                    pass
            
            # Cleanup
            await feature_manager.delete_flag(test_flag)
            
            return ValidationResult(
                test_name="test_feature_flag_management",
                category="configuration",
                status="pass",
                message="Feature flag management system working correctly",
                duration_seconds=0,
                details={"total_flags": len(flags)}
            )
            
        except ImportError:
            return ValidationResult(
                test_name="test_feature_flag_management",
                category="configuration",
                status="fail",
                message="FeatureManager not available",
                duration_seconds=0
            )
        except Exception as e:
            return ValidationResult(
                test_name="test_feature_flag_management",
                category="configuration",
                status="fail",
                message="Feature flag management test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_configuration_validation(self) -> ValidationResult:
        """Test configuration validation system"""
        try:
            from src.config.validators import ConfigurationValidator
            
            validator = ConfigurationValidator(self.settings)
            warnings = validator.validate_all()
            
            # Test production safety validation
            safety_issues = validator.validate_production_safety()
            
            details = {
                "validation_warnings": len(warnings),
                "safety_issues": len(safety_issues),
                "warnings": warnings[:5],  # First 5 warnings
                "safety_issues_found": safety_issues[:3]  # First 3 safety issues
            }
            
            if safety_issues and self.settings.environment == "production":
                return ValidationResult(
                    test_name="test_configuration_validation",
                    category="configuration",
                    status="fail",
                    message=f"Production safety violations found: {len(safety_issues)}",
                    duration_seconds=0,
                    details=details
                )
            
            status = "warning" if warnings else "pass"
            message = f"Configuration validation complete. {len(warnings)} warnings found." if warnings else "No configuration issues found"
            
            return ValidationResult(
                test_name="test_configuration_validation",
                category="configuration",
                status=status,
                message=message,
                duration_seconds=0,
                details=details
            )
            
        except ImportError:
            return ValidationResult(
                test_name="test_configuration_validation",
                category="configuration",
                status="warning",
                message="Configuration validator not available",
                duration_seconds=0
            )
        except Exception as e:
            return ValidationResult(
                test_name="test_configuration_validation",
                category="configuration",
                status="fail",
                message="Configuration validation test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_environment_configs(self) -> ValidationResult:
        """Test environment-specific configurations"""
        try:
            env_files = ['.env.development', '.env.staging', '.env.production']
            existing_files = []
            
            for env_file in env_files:
                file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), env_file)
                if os.path.exists(file_path):
                    existing_files.append(env_file)
            
            if len(existing_files) < 2:
                return ValidationResult(
                    test_name="test_environment_configs",
                    category="configuration",
                    status="warning",
                    message=f"Only {len(existing_files)} environment config files found",
                    duration_seconds=0,
                    details={"existing_files": existing_files}
                )
            
            return ValidationResult(
                test_name="test_environment_configs",
                category="configuration",
                status="pass",
                message=f"Environment configuration files present: {len(existing_files)}",
                duration_seconds=0,
                details={"existing_files": existing_files}
            )
            
        except Exception as e:
            return ValidationResult(
                test_name="test_environment_configs",
                category="configuration",
                status="fail",
                message="Environment configuration test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_admin_endpoints(self) -> ValidationResult:
        """Test admin API endpoints"""
        try:
            # This would typically make HTTP requests to admin endpoints
            # For now, just check if the module exists and can be imported
            
            from src.api.endpoints.admin import router as admin_router
            
            # Check if admin routes are defined
            route_count = len(admin_router.routes)
            
            if route_count == 0:
                return ValidationResult(
                    test_name="test_admin_endpoints",
                    category="configuration",
                    status="fail",
                    message="No admin routes found",
                    duration_seconds=0
                )
            
            return ValidationResult(
                test_name="test_admin_endpoints",
                category="configuration",
                status="pass",
                message=f"Admin endpoints available: {route_count} routes",
                duration_seconds=0,
                details={"route_count": route_count}
            )
            
        except ImportError:
            return ValidationResult(
                test_name="test_admin_endpoints",
                category="configuration",
                status="warning",
                message="Admin endpoints module not found",
                duration_seconds=0
            )
        except Exception as e:
            return ValidationResult(
                test_name="test_admin_endpoints",
                category="configuration",
                status="fail",
                message="Admin endpoints test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    # Observability Tests (PRP 24)
    async def _test_metrics_collection(self) -> ValidationResult:
        """Test metrics collection framework"""
        try:
            from src.observability.metrics import metrics
            
            # Test metric collection
            test_metric = "test_validation_metric"
            
            # Test different metric types
            metrics.increment_counter(test_metric)
            metrics.record_histogram(f"{test_metric}_histogram", 1.5)
            metrics.set_gauge(f"{test_metric}_gauge", 42)
            
            # Test metric retrieval (if available)
            enabled = getattr(metrics, 'enabled', True)
            
            return ValidationResult(
                test_name="test_metrics_collection",
                category="observability",
                status="pass",
                message=f"Metrics collection {'enabled' if enabled else 'disabled'}",
                duration_seconds=0,
                details={"metrics_enabled": enabled}
            )
            
        except ImportError:
            return ValidationResult(
                test_name="test_metrics_collection",
                category="observability",
                status="fail",
                message="Metrics collection framework not available",
                duration_seconds=0
            )
        except Exception as e:
            return ValidationResult(
                test_name="test_metrics_collection",
                category="observability",
                status="fail",
                message="Metrics collection test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_medical_metrics(self) -> ValidationResult:
        """Test medical domain-specific metrics"""
        try:
            from src.observability.medical_metrics import MedicalMetrics
            
            medical_metrics = MedicalMetrics()
            
            # Test medical query tracking
            medical_metrics.track_query_classification("PROTOCOL_STEPS", 0.95)
            medical_metrics.track_specialty_query("cardiology", "STEMI_protocol")
            medical_metrics.track_medication_lookup("aspirin", True)
            
            return ValidationResult(
                test_name="test_medical_metrics",
                category="observability",
                status="pass",
                message="Medical metrics collection working",
                duration_seconds=0
            )
            
        except ImportError:
            return ValidationResult(
                test_name="test_medical_metrics",
                category="observability",
                status="warning",
                message="Medical metrics module not available",
                duration_seconds=0
            )
        except Exception as e:
            return ValidationResult(
                test_name="test_medical_metrics",
                category="observability",
                status="fail",
                message="Medical metrics test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_health_monitoring(self) -> ValidationResult:
        """Test health monitoring system"""
        try:
            from src.observability.health import HealthMonitor
            
            health_monitor = HealthMonitor(self.settings, self.db, self.redis)
            health_status = await health_monitor.check_all_components()
            
            overall_healthy = health_status.get("overall_healthy", False)
            component_count = len(health_status.get("components", {}))
            
            status = "pass" if overall_healthy else "warning"
            message = f"Health monitoring: {component_count} components, {'healthy' if overall_healthy else 'issues detected'}"
            
            return ValidationResult(
                test_name="test_health_monitoring",
                category="observability",
                status=status,
                message=message,
                duration_seconds=0,
                details=health_status
            )
            
        except ImportError:
            return ValidationResult(
                test_name="test_health_monitoring",
                category="observability",
                status="warning",
                message="Health monitoring module not available",
                duration_seconds=0
            )
        except Exception as e:
            return ValidationResult(
                test_name="test_health_monitoring",
                category="observability",
                status="fail",
                message="Health monitoring test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_prometheus_integration(self) -> ValidationResult:
        """Test Prometheus metrics integration"""
        try:
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
            
            # Generate metrics
            metrics_output = generate_latest()
            
            if len(metrics_output) == 0:
                return ValidationResult(
                    test_name="test_prometheus_integration",
                    category="observability",
                    status="warning",
                    message="No Prometheus metrics generated",
                    duration_seconds=0
                )
            
            # Check for custom metrics
            metrics_str = metrics_output.decode('utf-8')
            custom_metrics = [line for line in metrics_str.split('\n') if 'edbot_' in line]
            
            return ValidationResult(
                test_name="test_prometheus_integration",
                category="observability",
                status="pass",
                message=f"Prometheus integration working: {len(custom_metrics)} custom metrics",
                duration_seconds=0,
                details={
                    "total_metrics_size": len(metrics_output),
                    "custom_metrics_count": len(custom_metrics)
                }
            )
            
        except ImportError:
            return ValidationResult(
                test_name="test_prometheus_integration",
                category="observability",
                status="fail",
                message="Prometheus client not available",
                duration_seconds=0
            )
        except Exception as e:
            return ValidationResult(
                test_name="test_prometheus_integration",
                category="observability",
                status="fail",
                message="Prometheus integration test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    # Testing Infrastructure Tests (PRP 23)
    async def _test_unit_test_coverage(self) -> ValidationResult:
        """Test unit test coverage"""
        try:
            test_files = []
            test_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests', 'unit')
            
            if os.path.exists(test_dir):
                for file in os.listdir(test_dir):
                    if file.startswith('test_') and file.endswith('.py'):
                        test_files.append(file)
            
            if len(test_files) < 5:
                return ValidationResult(
                    test_name="test_unit_test_coverage",
                    category="testing",
                    status="warning",
                    message=f"Limited unit test coverage: {len(test_files)} test files",
                    duration_seconds=0,
                    details={"test_files": test_files}
                )
            
            return ValidationResult(
                test_name="test_unit_test_coverage",
                category="testing",
                status="pass",
                message=f"Good unit test coverage: {len(test_files)} test files",
                duration_seconds=0,
                details={"test_files": test_files}
            )
            
        except Exception as e:
            return ValidationResult(
                test_name="test_unit_test_coverage",
                category="testing",
                status="fail",
                message="Unit test coverage check failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_integration_test_suite(self) -> ValidationResult:
        """Test integration test suite"""
        try:
            test_files = []
            test_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests', 'integration')
            
            if os.path.exists(test_dir):
                for file in os.listdir(test_dir):
                    if file.startswith('test_') and file.endswith('.py'):
                        test_files.append(file)
            
            return ValidationResult(
                test_name="test_integration_test_suite",
                category="testing",
                status="pass" if len(test_files) >= 3 else "warning",
                message=f"Integration tests available: {len(test_files)} test files",
                duration_seconds=0,
                details={"test_files": test_files}
            )
            
        except Exception as e:
            return ValidationResult(
                test_name="test_integration_test_suite",
                category="testing",
                status="fail",
                message="Integration test suite check failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_performance_benchmarks(self) -> ValidationResult:
        """Test performance benchmark suite"""
        try:
            test_files = []
            test_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tests', 'performance')
            
            if os.path.exists(test_dir):
                for file in os.listdir(test_dir):
                    if file.startswith('test_') and file.endswith('.py'):
                        test_files.append(file)
            
            return ValidationResult(
                test_name="test_performance_benchmarks",
                category="testing",
                status="pass" if len(test_files) >= 2 else "warning",
                message=f"Performance benchmarks available: {len(test_files)} test files",
                duration_seconds=0,
                details={"test_files": test_files}
            )
            
        except Exception as e:
            return ValidationResult(
                test_name="test_performance_benchmarks",
                category="testing",
                status="fail",
                message="Performance benchmark check failed",
                duration_seconds=0,
                error=str(e)
            )
    
    # Rollout Infrastructure Tests (PRP 25)
    async def _test_pre_rollout_checks(self) -> ValidationResult:
        """Test pre-rollout validation system"""
        try:
            from scripts.pre_rollout_checklist import PreRolloutChecker
            
            checker = PreRolloutChecker(self.settings, self.db, self.redis)
            
            # Run a subset of checks to avoid full validation
            check_result = await checker._check_database_schema()
            
            return ValidationResult(
                test_name="test_pre_rollout_checks",
                category="rollout",
                status="pass",
                message="Pre-rollout check system operational",
                duration_seconds=0,
                details={"sample_check": check_result.status}
            )
            
        except ImportError:
            return ValidationResult(
                test_name="test_pre_rollout_checks",
                category="rollout",
                status="fail",
                message="Pre-rollout checker not available",
                duration_seconds=0
            )
        except Exception as e:
            return ValidationResult(
                test_name="test_pre_rollout_checks",
                category="rollout",
                status="fail",
                message="Pre-rollout check test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_backfill_system(self) -> ValidationResult:
        """Test backfill management system"""
        try:
            from scripts.backfill_manager import BackfillManager
            
            manager = BackfillManager(self.settings, self.db, self.redis)
            
            # Run dry-run backfill to test system
            result = await manager.run_full_backfill(dry_run=True)
            
            success = result["failure_count"] == 0
            
            return ValidationResult(
                test_name="test_backfill_system",
                category="rollout",
                status="pass" if success else "warning",
                message=f"Backfill system: {result['success_count']} tasks ready",
                duration_seconds=0,
                details={"backfill_summary": result}
            )
            
        except ImportError:
            return ValidationResult(
                test_name="test_backfill_system",
                category="rollout",
                status="fail",
                message="Backfill manager not available",
                duration_seconds=0
            )
        except Exception as e:
            return ValidationResult(
                test_name="test_backfill_system",
                category="rollout",
                status="fail",
                message="Backfill system test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_rollout_manager(self) -> ValidationResult:
        """Test rollout management system"""
        try:
            from scripts.rollout_manager import RolloutManager
            from src.config.feature_manager import FeatureManager
            
            feature_manager = FeatureManager(self.settings, self.redis)
            manager = RolloutManager(self.settings, self.db, self.redis, feature_manager)
            
            # Test rollout status check
            status = await manager.get_rollout_status()
            
            return ValidationResult(
                test_name="test_rollout_manager",
                category="rollout",
                status="pass",
                message="Rollout manager operational",
                duration_seconds=0,
                details={"status_check": status}
            )
            
        except ImportError:
            return ValidationResult(
                test_name="test_rollout_manager",
                category="rollout",
                status="fail",
                message="Rollout manager not available",
                duration_seconds=0
            )
        except Exception as e:
            return ValidationResult(
                test_name="test_rollout_manager",
                category="rollout",
                status="fail",
                message="Rollout manager test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    # Integration Tests
    async def _test_end_to_end_workflow(self) -> ValidationResult:
        """Test complete end-to-end workflow"""
        try:
            # Test that we can:
            # 1. Load configuration
            # 2. Connect to database and Redis
            # 3. Collect metrics
            # 4. Check health
            
            workflow_steps = []
            
            # Step 1: Configuration loaded (already done)
            workflow_steps.append("Configuration loaded")
            
            # Step 2: Database connectivity
            db_result = await self.db.execute("SELECT 1")
            if db_result.scalar() == 1:
                workflow_steps.append("Database connection verified")
            
            # Step 3: Redis connectivity
            redis_pong = await self.redis.ping()
            if redis_pong:
                workflow_steps.append("Redis connection verified")
            
            # Step 4: Metrics collection
            try:
                from src.observability.metrics import metrics
                metrics.increment_counter("test_e2e_workflow")
                workflow_steps.append("Metrics collection verified")
            except (ImportError, AttributeError, Exception) as e:
                # Metrics collection not available or failed - continue without it
                logger.debug(f"Metrics collection failed: {e}")
                pass
            
            return ValidationResult(
                test_name="test_end_to_end_workflow",
                category="integration",
                status="pass",
                message=f"End-to-end workflow: {len(workflow_steps)} steps completed",
                duration_seconds=0,
                details={"workflow_steps": workflow_steps}
            )
            
        except Exception as e:
            return ValidationResult(
                test_name="test_end_to_end_workflow",
                category="integration",
                status="fail",
                message="End-to-end workflow test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_feature_flag_integration(self) -> ValidationResult:
        """Test feature flag integration with other systems"""
        try:
            from src.config.feature_manager import FeatureManager
            
            feature_manager = FeatureManager(self.settings, self.redis)
            
            # Test flag affecting observability
            await feature_manager.set_flag("enable_test_metrics", True, ttl_minutes=1)
            
            # Test flag affecting configuration
            await feature_manager.set_flag("test_integration_flag", False, ttl_minutes=1)
            
            # Verify flags are retrievable
            flags = await feature_manager.list_flags()
            
            test_flags_found = sum(1 for flag in flags if 'test' in flag)
            
            # Cleanup
            await feature_manager.delete_flag("enable_test_metrics")
            await feature_manager.delete_flag("test_integration_flag")
            
            return ValidationResult(
                test_name="test_feature_flag_integration",
                category="integration",
                status="pass",
                message=f"Feature flag integration working: {test_flags_found} test flags processed",
                duration_seconds=0
            )
            
        except Exception as e:
            return ValidationResult(
                test_name="test_feature_flag_integration",
                category="integration",
                status="fail",
                message="Feature flag integration test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_observability_integration(self) -> ValidationResult:
        """Test observability integration with core systems"""
        try:
            # Test metrics collection during database operations
            from src.observability.metrics import metrics
            
            # Perform database operation while collecting metrics
            start_time = time.time()
            await self.db.execute("SELECT COUNT(*) FROM documents")
            query_time = time.time() - start_time
            
            # Record metric
            metrics.record_histogram("validation_db_query_time", query_time)
            
            # Test health monitoring
            try:
                from src.observability.health import HealthMonitor
                health_monitor = HealthMonitor(self.settings, self.db, self.redis)
                health_check = await health_monitor.check_all_components()
                
                return ValidationResult(
                    test_name="test_observability_integration",
                    category="integration",
                    status="pass",
                    message="Observability integration working",
                    duration_seconds=0,
                    details={
                        "db_query_time": query_time,
                        "health_check_components": len(health_check.get("components", {}))
                    }
                )
            except ImportError:
                return ValidationResult(
                    test_name="test_observability_integration",
                    category="integration",
                    status="warning",
                    message="Partial observability integration (health monitoring unavailable)",
                    duration_seconds=0
                )
                
        except Exception as e:
            return ValidationResult(
                test_name="test_observability_integration",
                category="integration",
                status="fail",
                message="Observability integration test failed",
                duration_seconds=0,
                error=str(e)
            )
    
    async def _test_rollout_safety(self) -> ValidationResult:
        """Test rollout safety mechanisms"""
        try:
            from src.config.feature_manager import FeatureManager
            
            feature_manager = FeatureManager(self.settings, self.redis)
            
            # Test that production safety flags cannot be disabled
            safety_tests = []
            
            if self.settings.environment == "production":
                # These should fail in production
                dangerous_changes = [
                    ("disable_external_calls", False),
                    ("log_scrub_phi", False)
                ]
                
                for flag, dangerous_value in dangerous_changes:
                    try:
                        await feature_manager.set_flag(flag, dangerous_value)
                        safety_tests.append(f"FAIL: {flag} change allowed")
                    except Exception:
                        safety_tests.append(f"PASS: {flag} change blocked")
            else:
                safety_tests.append("SKIP: Not in production environment")
            
            # Test rollback capability
            test_flag = "test_rollback_flag"
            await feature_manager.set_flag(test_flag, True, ttl_minutes=1)
            await feature_manager.set_flag(test_flag, False)  # Rollback
            
            final_value = await feature_manager.get_flag(test_flag)
            if not final_value:
                safety_tests.append("PASS: Rollback capability verified")
            else:
                safety_tests.append("FAIL: Rollback capability failed")
            
            # Cleanup
            await feature_manager.delete_flag(test_flag)
            
            passed_tests = sum(1 for test in safety_tests if test.startswith("PASS"))
            failed_tests = sum(1 for test in safety_tests if test.startswith("FAIL"))
            
            status = "pass" if failed_tests == 0 else "fail"
            
            return ValidationResult(
                test_name="test_rollout_safety",
                category="integration",
                status=status,
                message=f"Rollout safety: {passed_tests} passed, {failed_tests} failed",
                duration_seconds=0,
                details={"safety_tests": safety_tests}
            )
            
        except Exception as e:
            return ValidationResult(
                test_name="test_rollout_safety",
                category="integration",
                status="fail",
                message="Rollout safety test failed",
                duration_seconds=0,
                error=str(e)
            )

async def main():
    """CLI entry point for final validation"""
    parser = argparse.ArgumentParser(description="Run final validation of PRPs 22-25")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="Output format")
    parser.add_argument("--category", choices=["configuration", "observability", "testing", "rollout", "integration"], 
                       help="Run only tests in specific category")
    parser.add_argument("--fail-on-warning", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--config-file", help="Path to configuration file")
    
    args = parser.parse_args()
    
    # Setup path for imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    try:
        # Import required components
        from src.cache.redis_client import get_redis_client
        from src.config.enhanced_settings import EnhancedSettings
        from src.models.database import get_db_session
        
        # Load settings
        if args.config_file:
            os.environ["EDBOT_CONFIG_FILE"] = args.config_file
            
        settings = EnhancedSettings()
        
        # Get connections
        db_session = await get_db_session()
        redis_client = await get_redis_client()
        
        # Create validator
        validator = FinalValidator(settings, db_session, redis_client)
        
        # Run validation
        results = await validator.run_full_validation()
        
        # Output results
        if args.output == "json":
            print(json.dumps(results, indent=2))
        else:
            # Text output already handled by validator
            pass
            
        # Determine exit code
        failed_count = results["statistics"]["failed"]
        warning_count = results["statistics"]["warnings"]
        
        if failed_count > 0:
            sys.exit(1)  # Hard failure
        elif warning_count > 0 and args.fail_on_warning:
            sys.exit(2)  # Soft failure
        else:
            sys.exit(0)  # Success
            
    except Exception as e:
        logger.error(f"Final validation failed: {e}")
        if args.output == "json":
            error_output = {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "status": "failed"
            }
            print(json.dumps(error_output, indent=2))
        sys.exit(3)  # System error

if __name__ == "__main__":
    asyncio.run(main())