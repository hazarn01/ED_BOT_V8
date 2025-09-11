#!/usr/bin/env python3
"""
Pre-rollout validation checklist for EDBotv8
Validates system readiness before deploying new features
"""

import asyncio
import importlib.util
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CheckResult:
    """Result of a pre-rollout validation check"""
    name: str
    status: str  # "pass", "fail", "warning"
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()

class PreRolloutChecker:
    """Pre-rollout validation and preparation"""
    
    def __init__(self, settings, db_session, redis_client, es_client=None):
        self.settings = settings
        self.db = db_session
        self.redis = redis_client
        self.es_client = es_client
        self.logger = logging.getLogger(__name__)
        
    async def run_all_checks(self) -> List[CheckResult]:
        """Run comprehensive pre-rollout checks"""
        self.logger.info("Starting pre-rollout validation checks...")
        
        checks = []
        
        # Run all validation checks
        check_functions = [
            self._check_database_schema,
            self._check_elasticsearch_setup,
            self._check_feature_flags,
            self._check_dependencies,
            self._check_performance_baseline,
            self._check_backup_status,
            self._check_monitoring_setup
        ]
        
        for check_func in check_functions:
            try:
                result = await check_func()
                checks.append(result)
                
                # Log result
                status_symbol = "✓" if result.status == "pass" else "⚠" if result.status == "warning" else "✗"
                self.logger.info(f"{status_symbol} {result.name}: {result.message}")
                
            except Exception as e:
                error_result = CheckResult(
                    name=check_func.__name__.replace('_check_', ''),
                    status="fail",
                    message=f"Check failed with exception: {e}",
                    details={"exception": str(e)}
                )
                checks.append(error_result)
                self.logger.error(f"✗ {error_result.name}: {error_result.message}")
        
        # Log summary
        passed = sum(1 for c in checks if c.status == "pass")
        failed = sum(1 for c in checks if c.status == "fail")
        warnings = sum(1 for c in checks if c.status == "warning")
        
        self.logger.info(f"\nPre-rollout check summary: {passed} passed, {failed} failed, {warnings} warnings")
        
        if failed > 0:
            self.logger.error("❌ Pre-rollout checks FAILED - deployment should be blocked")
        elif warnings > 0:
            self.logger.warning("⚠️  Pre-rollout checks passed with warnings - review before proceeding")
        else:
            self.logger.info("✅ All pre-rollout checks PASSED - ready for deployment")
        
        return checks
        
    async def _check_database_schema(self) -> CheckResult:
        """Verify database schema is ready"""
        try:
            # Check if new tables exist
            tables_to_check = [
                "extracted_tables",
                "query_response_cache", 
                "document_chunks"  # Should have new highlight columns
            ]
            
            missing_tables = []
            for table in tables_to_check:
                result = await self.db.execute(
                    f"SELECT to_regclass('public.{table}')"
                )
                if result.scalar() is None:
                    missing_tables.append(table)
                    
            if missing_tables:
                return CheckResult(
                    "database_schema",
                    "fail", 
                    f"Missing required tables: {', '.join(missing_tables)}",
                    {"missing_tables": missing_tables}
                )
                
            # Check for new columns in document_chunks for highlighting
            chunk_columns_result = await self.db.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'document_chunks' 
                AND column_name IN ('page_number', 'page_span_start', 'bbox')
            """)
            
            expected_columns = {"page_number", "page_span_start", "bbox"}
            existing_columns = {row[0] for row in chunk_columns_result}
            missing_columns = expected_columns - existing_columns
            
            if missing_columns:
                return CheckResult(
                    "database_schema",
                    "warning",
                    f"Missing highlighting columns: {', '.join(missing_columns)} - source highlighting will be limited",
                    {"missing_columns": list(missing_columns)}
                )
            
            # Check table counts for basic sanity
            counts = {}
            for table in tables_to_check:
                if table not in missing_tables:
                    count_result = await self.db.execute(f"SELECT COUNT(*) FROM {table}")
                    counts[table] = count_result.scalar()
            
            return CheckResult(
                "database_schema",
                "pass",
                f"All required tables present. Counts: {counts}",
                {"table_counts": counts, "highlighting_columns_present": len(missing_columns) == 0}
            )
            
        except Exception as e:
            return CheckResult(
                "database_schema",
                "fail",
                f"Database schema check failed: {e}",
                {"exception": str(e)}
            )
            
    async def _check_elasticsearch_setup(self) -> CheckResult:
        """Verify Elasticsearch is ready if hybrid search enabled"""
        try:
            # Check if Elasticsearch is enabled in configuration
            es_enabled = getattr(self.settings.features, 'enable_elasticsearch', False)
            
            if not es_enabled:
                return CheckResult(
                    "elasticsearch_setup",
                    "pass",
                    "Elasticsearch not enabled - hybrid search will use pgvector only"
                )
            
            if not self.es_client:
                return CheckResult(
                    "elasticsearch_setup",
                    "fail",
                    "Elasticsearch enabled but client not available"
                )
                
            # Try to get Elasticsearch client
            es = await self.es_client.get_client() if hasattr(self.es_client, 'get_client') else self.es_client
            if not es:
                return CheckResult(
                    "elasticsearch_setup",
                    "fail",
                    "Elasticsearch client not available"
                )
                
            # Check cluster health
            health = await es.cluster.health()
            if health["status"] == "red":
                return CheckResult(
                    "elasticsearch_setup",
                    "fail",
                    f"Elasticsearch cluster unhealthy: {health['status']}",
                    {"cluster_health": health}
                )
                
            # Check if indices exist
            index_prefix = getattr(self.settings, 'elasticsearch_index_prefix', 'edbot')
            indices = [
                f"{index_prefix}_documents",
                f"{index_prefix}_chunks"
            ]
            
            missing_indices = []
            index_counts = {}
            
            for index in indices:
                exists = await es.indices.exists(index=index)
                if not exists:
                    missing_indices.append(index)
                else:
                    # Get document count
                    count_result = await es.count(index=index)
                    index_counts[index] = count_result["count"]
                    
            if missing_indices:
                return CheckResult(
                    "elasticsearch_setup",
                    "warning",
                    f"Elasticsearch indices need to be created: {', '.join(missing_indices)}",
                    {"missing_indices": missing_indices, "existing_indices": index_counts}
                )
                
            return CheckResult(
                "elasticsearch_setup",
                "pass",
                f"Elasticsearch ready - cluster status: {health['status']}, indices: {len(index_counts)}",
                {"cluster_health": health, "index_counts": index_counts}
            )
            
        except Exception as e:
            return CheckResult(
                "elasticsearch_setup",
                "fail",
                f"Elasticsearch check failed: {e}",
                {"exception": str(e)}
            )
            
    async def _check_feature_flags(self) -> CheckResult:
        """Validate feature flag configuration"""
        try:
            # Import configuration validator
            try:
                from src.config.validators import ConfigurationValidator
                
                validator = ConfigurationValidator(self.settings)
                warnings = validator.validate_all()
                
                # Check production safety
                production_safety_ok = True
                safety_issues = []
                
                if hasattr(self.settings, 'environment') and self.settings.environment == 'production':
                    # In production, certain safety features must be enabled
                    safety_flags = {
                        'log_scrub_phi': True,
                        'disable_external_calls': True,
                        'enable_safety_validation': True
                    }
                    
                    for flag, required_value in safety_flags.items():
                        current_value = getattr(self.settings, flag, None)
                        if current_value != required_value:
                            production_safety_ok = False
                            safety_issues.append(f"{flag} should be {required_value}, got {current_value}")
                
                if not production_safety_ok:
                    return CheckResult(
                        "feature_flags",
                        "fail",
                        f"Production safety requirements not met: {', '.join(safety_issues)}",
                        {"safety_issues": safety_issues, "validation_warnings": warnings}
                    )
                
                if warnings:
                    return CheckResult(
                        "feature_flags",
                        "warning",
                        f"Configuration validation warnings: {len(warnings)} issues found",
                        {"warnings": warnings}
                    )
                    
                # Check feature flag coherence
                feature_issues = []
                
                # If hybrid search is enabled, check dependencies
                if getattr(self.settings.features, 'enable_elasticsearch', False):
                    if not hasattr(self.settings, 'elasticsearch_url') or not self.settings.elasticsearch_url:
                        feature_issues.append("Elasticsearch enabled but no URL configured")
                
                # If table extraction is enabled, check unstructured is available
                if getattr(self.settings.features, 'enable_table_extraction', False):
                    try:
                        import unstructured
                    except ImportError:
                        feature_issues.append("Table extraction enabled but unstructured package not available")
                
                if feature_issues:
                    return CheckResult(
                        "feature_flags",
                        "warning",
                        f"Feature flag dependency issues: {', '.join(feature_issues)}",
                        {"feature_issues": feature_issues}
                    )
                    
                return CheckResult(
                    "feature_flags",
                    "pass",
                    "Feature flag configuration valid and production-safe"
                )
                
            except ImportError:
                return CheckResult(
                    "feature_flags",
                    "warning",
                    "Configuration validator not available - skipping advanced validation"
                )
            
        except Exception as e:
            return CheckResult(
                "feature_flags",
                "fail",
                f"Feature flag validation failed: {e}",
                {"exception": str(e)}
            )
            
    async def _check_dependencies(self) -> CheckResult:
        """Check required dependencies are installed"""
        try:
            required_packages = {
                "unstructured": "table extraction",
                "elasticsearch": "hybrid search", 
                "streamlit": "demo UI",
                "prometheus_client": "metrics collection",
                "redis": "caching and feature flags",
                "sqlalchemy": "database ORM",
                "fastapi": "API framework",
                "pydantic": "data validation"
            }
            
            missing = []
            available = []
            
            for package, purpose in required_packages.items():
                try:
                    spec = importlib.util.find_spec(package)
                    if spec is None:
                        missing.append(f"{package} ({purpose})")
                    else:
                        available.append(f"{package} ({purpose})")
                except ImportError:
                    missing.append(f"{package} ({purpose})")
                    
            # Check Python version
            python_version = sys.version_info
            if python_version < (3, 8):
                return CheckResult(
                    "dependencies",
                    "fail",
                    f"Python {python_version.major}.{python_version.minor} too old, requires 3.8+",
                    {"python_version": f"{python_version.major}.{python_version.minor}.{python_version.micro}"}
                )
                
            if missing:
                # Distinguish between critical and optional missing packages
                critical_missing = [pkg for pkg in missing if any(
                    critical in pkg.lower() for critical in ['sqlalchemy', 'fastapi', 'pydantic', 'redis']
                )]
                
                if critical_missing:
                    return CheckResult(
                        "dependencies",
                        "fail",
                        f"Critical dependencies missing: {', '.join(critical_missing)}",
                        {"missing_packages": missing, "available_packages": available}
                    )
                else:
                    return CheckResult(
                        "dependencies",
                        "warning",
                        f"Optional dependencies missing: {', '.join(missing)} - some features will be disabled",
                        {"missing_packages": missing, "available_packages": available}
                    )
                    
            return CheckResult(
                "dependencies",
                "pass",
                f"All dependencies available ({len(available)} packages)",
                {"available_packages": available, "python_version": f"{python_version.major}.{python_version.minor}.{python_version.micro}"}
            )
            
        except Exception as e:
            return CheckResult(
                "dependencies",
                "fail",
                f"Dependency check failed: {e}",
                {"exception": str(e)}
            )
        
    async def _check_performance_baseline(self) -> CheckResult:
        """Establish performance baseline"""
        try:
            import time
            
            measurements = {}
            
            # Test basic database query performance
            start = time.time()
            result = await self.db.execute("SELECT COUNT(*) FROM documents")
            db_time = time.time() - start
            doc_count = result.scalar()
            measurements["db_query_time"] = db_time
            measurements["document_count"] = doc_count
            
            # Test Redis performance
            start = time.time()
            await self.redis.ping()
            redis_time = time.time() - start
            measurements["redis_ping_time"] = redis_time
            
            # Test more complex database query
            start = time.time()
            chunk_result = await self.db.execute("SELECT COUNT(*) FROM document_chunks")
            complex_db_time = time.time() - start
            chunk_count = chunk_result.scalar()
            measurements["complex_db_time"] = complex_db_time
            measurements["chunk_count"] = chunk_count
            
            # Test Redis set/get performance
            test_key = "performance_test"
            test_value = json.dumps({"test": "data", "timestamp": datetime.utcnow().isoformat()})
            
            start = time.time()
            await self.redis.set(test_key, test_value, ex=60)
            redis_set_time = time.time() - start
            
            start = time.time()
            await self.redis.get(test_key)
            redis_get_time = time.time() - start
            measurements["redis_set_time"] = redis_set_time
            measurements["redis_get_time"] = redis_get_time
            
            # Clean up test key
            await self.redis.delete(test_key)
            
            baseline = {
                **measurements,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Store baseline for comparison during rollout
            await self.redis.set(
                "performance_baseline",
                json.dumps(baseline),
                ex=3600  # 1 hour
            )
            
            # Check if performance is acceptable
            performance_issues = []
            
            if db_time > 1.0:
                performance_issues.append(f"Database query slow: {db_time:.3f}s")
            if redis_time > 0.1:
                performance_issues.append(f"Redis ping slow: {redis_time:.3f}s")
            if doc_count == 0:
                performance_issues.append("No documents in database")
                
            if performance_issues:
                return CheckResult(
                    "performance_baseline",
                    "warning",
                    f"Performance issues detected: {', '.join(performance_issues)}",
                    baseline
                )
            
            return CheckResult(
                "performance_baseline",
                "pass",
                f"Baseline established: {doc_count} docs, DB {db_time:.3f}s, Redis {redis_time:.3f}s",
                baseline
            )
            
        except Exception as e:
            return CheckResult(
                "performance_baseline",
                "fail",
                f"Performance baseline check failed: {e}",
                {"exception": str(e)}
            )
            
    async def _check_backup_status(self) -> CheckResult:
        """Verify recent backups exist or database is accessible for backup"""
        try:
            # Test if we can create a schema dump (basic backup readiness)
            result = await self.db.execute("""
                SELECT schemaname, tablename, tableowner
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            
            tables = list(result)
            table_count = len(tables)
            
            if table_count == 0:
                return CheckResult(
                    "backup_status",
                    "fail",
                    "No tables found in public schema"
                )
            
            # Check if we can access table sizes (proxy for backup feasibility)
            size_result = await self.db.execute("""
                SELECT 
                    SUM(pg_total_relation_size(schemaname||'.'||tablename)) as total_size
                FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            
            total_size = size_result.scalar() or 0
            size_mb = total_size / (1024 * 1024)
            
            # Check disk space (if possible)
            disk_info = {}
            try:
                import shutil
                disk_usage = shutil.disk_usage(self.settings.docs_path if hasattr(self.settings, 'docs_path') else '/')
                disk_info = {
                    "total_gb": disk_usage.total / (1024**3),
                    "free_gb": disk_usage.free / (1024**3),
                    "used_gb": disk_usage.used / (1024**3)
                }
            except Exception as e:
                logger.debug(f"Could not get disk usage: {e}")
                pass
                
            backup_info = {
                "table_count": table_count,
                "database_size_mb": size_mb,
                "disk_info": disk_info,
                "backup_feasible": size_mb < 1000,  # Under 1GB is easily backupable
                "tables": [{"schema": row[0], "table": row[1], "owner": row[2]} for row in tables[:10]]  # First 10 tables
            }
            
            if size_mb > 5000:  # Over 5GB
                return CheckResult(
                    "backup_status",
                    "warning",
                    f"Large database ({size_mb:.1f}MB) - backup may take significant time",
                    backup_info
                )
            
            return CheckResult(
                "backup_status", 
                "pass",
                f"Database accessible for backup ({table_count} tables, {size_mb:.1f}MB)",
                backup_info
            )
            
        except Exception as e:
            return CheckResult(
                "backup_status",
                "warning",
                f"Backup readiness check failed: {e}",
                {"exception": str(e)}
            )
            
    async def _check_monitoring_setup(self) -> CheckResult:
        """Verify monitoring and alerting is configured"""
        try:
            monitoring_status = {}
            
            # Check if metrics collection is available
            try:
                from src.observability.metrics import metrics
                monitoring_status["metrics_available"] = True
                monitoring_status["metrics_enabled"] = getattr(metrics, 'enabled', False)
            except ImportError:
                monitoring_status["metrics_available"] = False
                monitoring_status["metrics_enabled"] = False
            
            # Check if health monitoring is available
            try:
                from src.observability.health import HealthMonitor
                monitoring_status["health_monitoring_available"] = True
            except ImportError:
                monitoring_status["health_monitoring_available"] = False
            
            # Check if Prometheus client is working
            try:
                from prometheus_client import generate_latest
                metrics_output = generate_latest()
                monitoring_status["prometheus_working"] = len(metrics_output) > 0
            except Exception:
                monitoring_status["prometheus_working"] = False
            
            # Check Redis for monitoring state
            try:
                monitoring_key = "system_monitoring_state"
                test_state = {"last_check": datetime.utcnow().isoformat(), "status": "testing"}
                await self.redis.set(monitoring_key, json.dumps(test_state), ex=300)
                retrieved_state = await self.redis.get(monitoring_key)
                monitoring_status["redis_monitoring_storage"] = retrieved_state is not None
                await self.redis.delete(monitoring_key)
            except Exception:
                monitoring_status["redis_monitoring_storage"] = False
            
            # Evaluate overall monitoring readiness
            critical_missing = []
            warnings = []
            
            if not monitoring_status.get("metrics_available", False):
                warnings.append("Metrics collection framework not available")
            elif not monitoring_status.get("metrics_enabled", False):
                warnings.append("Metrics collection disabled")
                
            if not monitoring_status.get("prometheus_working", False):
                warnings.append("Prometheus metrics not working")
                
            if not monitoring_status.get("redis_monitoring_storage", False):
                critical_missing.append("Redis not available for monitoring state")
                
            if critical_missing:
                return CheckResult(
                    "monitoring_setup",
                    "fail",
                    f"Critical monitoring components missing: {', '.join(critical_missing)}",
                    monitoring_status
                )
                
            if warnings:
                return CheckResult(
                    "monitoring_setup",
                    "warning",
                    f"Monitoring setup has issues: {', '.join(warnings)}",
                    monitoring_status
                )
            
            return CheckResult(
                "monitoring_setup",
                "pass",
                "Monitoring and observability configured",
                monitoring_status
            )
            
        except Exception as e:
            return CheckResult(
                "monitoring_setup",
                "warning",
                f"Monitoring setup check failed: {e}",
                {"exception": str(e)}
            )

async def main():
    """CLI entry point for pre-rollout checks"""
    import argparse
    import os
    import sys
    
    parser = argparse.ArgumentParser(description="Run pre-rollout validation checks")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="Output format")
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
        
        # Get database and Redis connections
        db_session = await get_db_session()
        redis_client = await get_redis_client()
        
        # Get Elasticsearch client if enabled
        es_client = None
        if getattr(settings.features, 'enable_elasticsearch', False):
            try:
                from src.search.elasticsearch_client import ElasticsearchClient
                es_client = ElasticsearchClient(settings)
            except ImportError:
                logger.warning("Elasticsearch enabled but client not available")
        
        # Run checks
        checker = PreRolloutChecker(settings, db_session, redis_client, es_client)
        results = await checker.run_all_checks()
        
        # Output results
        if args.output == "json":
            output = {
                "timestamp": datetime.utcnow().isoformat(),
                "total_checks": len(results),
                "passed": sum(1 for r in results if r.status == "pass"),
                "failed": sum(1 for r in results if r.status == "fail"),
                "warnings": sum(1 for r in results if r.status == "warning"),
                "checks": [asdict(result) for result in results]
            }
            print(json.dumps(output, indent=2))
        else:
            # Text output already handled by logger
            pass
            
        # Determine exit code
        failed_count = sum(1 for r in results if r.status == "fail")
        warning_count = sum(1 for r in results if r.status == "warning")
        
        if failed_count > 0:
            sys.exit(1)  # Hard failure
        elif warning_count > 0 and args.fail_on_warning:
            sys.exit(2)  # Soft failure
        else:
            sys.exit(0)  # Success
            
    except Exception as e:
        logger.error(f"Pre-rollout check failed: {e}")
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