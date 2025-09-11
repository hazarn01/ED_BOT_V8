# PRP 25: Backfill and Rollout Plan

## Problem Statement
The hybrid search and enhancement features require careful rollout to production with data backfill, feature validation, and rollback capabilities. The rollout must ensure zero downtime, data consistency, and the ability to quickly revert if issues arise.

## Success Criteria
- Zero-downtime deployment of new features
- All existing documents backfilled to new indices/tables
- Phased rollout with validation gates
- Quick rollback capability (<5 minutes)
- Data consistency maintained throughout
- Performance regressions detected early

## Implementation Approach

### 1. Pre-Rollout Preparation

```python
# scripts/pre_rollout_checklist.py
import asyncio
import logging
from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class CheckResult:
    name: str
    status: str  # "pass", "fail", "warning"
    message: str
    details: Dict[str, Any] = None

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
        checks = [
            await self._check_database_schema(),
            await self._check_elasticsearch_setup(),
            await self._check_feature_flags(),
            await self._check_dependencies(),
            await self._check_performance_baseline(),
            await self._check_backup_status(),
            await self._check_monitoring_setup()
        ]
        
        # Log summary
        passed = sum(1 for c in checks if c.status == "pass")
        failed = sum(1 for c in checks if c.status == "fail")
        warnings = sum(1 for c in checks if c.status == "warning")
        
        self.logger.info(f"Pre-rollout checks: {passed} passed, {failed} failed, {warnings} warnings")
        
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
                    f"Missing tables: {missing_tables}"
                )
                
            # Check for new columns in document_chunks
            chunk_columns = await self.db.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'document_chunks' 
                AND column_name IN ('page_number', 'page_span_start', 'bbox')
            """)
            
            expected_columns = {"page_number", "page_span_start", "bbox"}
            existing_columns = {row[0] for row in chunk_columns}
            missing_columns = expected_columns - existing_columns
            
            if missing_columns:
                return CheckResult(
                    "database_schema",
                    "warning",
                    f"Missing highlight columns: {missing_columns}",
                    {"missing_columns": list(missing_columns)}
                )
                
            return CheckResult(
                "database_schema",
                "pass",
                "All required tables and columns present"
            )
            
        except Exception as e:
            return CheckResult(
                "database_schema",
                "fail",
                f"Database check failed: {e}"
            )
            
    async def _check_elasticsearch_setup(self) -> CheckResult:
        """Verify Elasticsearch is ready if hybrid search enabled"""
        if not self.settings.features.enable_elasticsearch:
            return CheckResult(
                "elasticsearch_setup",
                "pass",
                "Elasticsearch not enabled"
            )
            
        try:
            es = self.es_client.get_client()
            if not es:
                return CheckResult(
                    "elasticsearch_setup",
                    "fail",
                    "Elasticsearch client not available"
                )
                
            # Check cluster health
            health = es.cluster.health()
            if health["status"] == "red":
                return CheckResult(
                    "elasticsearch_setup",
                    "fail",
                    f"Elasticsearch cluster unhealthy: {health['status']}"
                )
                
            # Check if indices exist
            indices = [
                f"{self.settings.elasticsearch_index_prefix}_documents",
                f"{self.settings.elasticsearch_index_prefix}_chunks"
            ]
            
            missing_indices = []
            for index in indices:
                if not es.indices.exists(index=index):
                    missing_indices.append(index)
                    
            if missing_indices:
                return CheckResult(
                    "elasticsearch_setup",
                    "warning",
                    f"Indices need to be created: {missing_indices}",
                    {"missing_indices": missing_indices}
                )
                
            return CheckResult(
                "elasticsearch_setup",
                "pass",
                f"Elasticsearch ready, status: {health['status']}"
            )
            
        except Exception as e:
            return CheckResult(
                "elasticsearch_setup",
                "fail",
                f"Elasticsearch check failed: {e}"
            )
            
    async def _check_feature_flags(self) -> CheckResult:
        """Validate feature flag configuration"""
        try:
            from src.config.validators import ConfigurationValidator
            
            validator = ConfigurationValidator(self.settings)
            warnings = validator.validate_all()
            
            if warnings:
                return CheckResult(
                    "feature_flags",
                    "warning",
                    f"Configuration warnings: {len(warnings)}",
                    {"warnings": warnings}
                )
                
            return CheckResult(
                "feature_flags",
                "pass",
                "Feature flag configuration valid"
            )
            
        except Exception as e:
            return CheckResult(
                "feature_flags",
                "fail",
                f"Feature flag validation failed: {e}"
            )
            
    async def _check_dependencies(self) -> CheckResult:
        """Check required dependencies are installed"""
        required_packages = {
            "unstructured": "table extraction",
            "elasticsearch": "hybrid search", 
            "streamlit": "demo UI",
            "prometheus_client": "metrics"
        }
        
        missing = []
        for package, purpose in required_packages.items():
            try:
                __import__(package)
            except ImportError:
                missing.append(f"{package} ({purpose})")
                
        if missing:
            return CheckResult(
                "dependencies",
                "warning",
                f"Optional dependencies missing: {missing}",
                {"missing_packages": missing}
            )
            
        return CheckResult(
            "dependencies",
            "pass",
            "All dependencies available"
        )
        
    async def _check_performance_baseline(self) -> CheckResult:
        """Establish performance baseline"""
        try:
            import time
            
            # Test basic query performance
            start = time.time()
            result = await self.db.execute("SELECT COUNT(*) FROM documents")
            db_time = time.time() - start
            
            doc_count = result.scalar()
            
            # Test Redis
            start = time.time()
            await self.redis.ping()
            redis_time = time.time() - start
            
            baseline = {
                "document_count": doc_count,
                "db_query_time": db_time,
                "redis_ping_time": redis_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Store baseline for comparison
            await self.redis.set(
                "performance_baseline",
                json.dumps(baseline),
                ex=3600  # 1 hour
            )
            
            return CheckResult(
                "performance_baseline",
                "pass",
                f"Baseline established: {doc_count} docs, DB {db_time:.3f}s",
                baseline
            )
            
        except Exception as e:
            return CheckResult(
                "performance_baseline",
                "fail",
                f"Baseline check failed: {e}"
            )
            
    async def _check_backup_status(self) -> CheckResult:
        """Verify recent backups exist"""
        # This would integrate with actual backup system
        # For now, just verify we can dump schema
        try:
            # Test if we can create a schema dump
            result = await self.db.execute("""
                SELECT schemaname, tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
            """)
            
            table_count = len(list(result))
            
            return CheckResult(
                "backup_status", 
                "pass",
                f"Database accessible for backup ({table_count} tables)"
            )
            
        except Exception as e:
            return CheckResult(
                "backup_status",
                "warning",
                f"Backup verification failed: {e}"
            )
            
    async def _check_monitoring_setup(self) -> CheckResult:
        """Verify monitoring and alerting is configured"""
        try:
            # Check if metrics endpoint is accessible
            from src.observability.metrics import metrics
            
            if not metrics.enabled:
                return CheckResult(
                    "monitoring_setup",
                    "warning",
                    "Metrics collection disabled"
                )
                
            return CheckResult(
                "monitoring_setup",
                "pass",
                "Monitoring configured"
            )
            
        except Exception as e:
            return CheckResult(
                "monitoring_setup",
                "warning",
                f"Monitoring check failed: {e}"
            )
```

### 2. Backfill Scripts

```python
# scripts/backfill_manager.py
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import json

class BackfillManager:
    """Manages data backfill operations"""
    
    def __init__(self, settings, db_session, es_client=None):
        self.settings = settings
        self.db = db_session
        self.es_client = es_client
        self.logger = logging.getLogger(__name__)
        
    async def run_full_backfill(self, dry_run: bool = True) -> Dict[str, Any]:
        """Run complete backfill process"""
        
        backfill_tasks = []
        
        # 1. Elasticsearch indices (if hybrid search enabled)
        if self.settings.features.enable_elasticsearch:
            backfill_tasks.append(("elasticsearch", self._backfill_elasticsearch))
            
        # 2. Source highlighting data
        if self.settings.features.enable_source_highlighting:
            backfill_tasks.append(("highlighting", self._backfill_highlighting_data))
            
        # 3. Table extraction
        if self.settings.features.enable_table_extraction:
            backfill_tasks.append(("tables", self._backfill_table_extraction))
            
        results = {}
        total_start = datetime.utcnow()
        
        for task_name, task_func in backfill_tasks:
            self.logger.info(f"Starting backfill: {task_name}")
            start_time = datetime.utcnow()
            
            try:
                result = await task_func(dry_run=dry_run)
                duration = (datetime.utcnow() - start_time).total_seconds()
                
                results[task_name] = {
                    "status": "success",
                    "duration_seconds": duration,
                    "details": result
                }
                
                self.logger.info(f"Completed {task_name} in {duration:.2f}s")
                
            except Exception as e:
                duration = (datetime.utcnow() - start_time).total_seconds()
                results[task_name] = {
                    "status": "failed",
                    "duration_seconds": duration,
                    "error": str(e)
                }
                self.logger.error(f"Failed {task_name}: {e}")
                
        total_duration = (datetime.utcnow() - total_start).total_seconds()
        
        summary = {
            "dry_run": dry_run,
            "total_duration_seconds": total_duration,
            "tasks": results,
            "success_count": sum(1 for r in results.values() if r["status"] == "success"),
            "failure_count": sum(1 for r in results.values() if r["status"] == "failed")
        }
        
        self.logger.info(f"Backfill complete: {summary['success_count']} success, {summary['failure_count']} failed")
        
        return summary
        
    async def _backfill_elasticsearch(self, dry_run: bool = True) -> Dict[str, Any]:
        """Backfill Elasticsearch indices"""
        from scripts.backfill_elasticsearch import backfill_to_elasticsearch
        
        if dry_run:
            # Count what would be backfilled
            doc_count = await self.db.scalar("SELECT COUNT(*) FROM documents")
            chunk_count = await self.db.scalar("SELECT COUNT(*) FROM document_chunks")
            
            return {
                "documents_to_index": doc_count,
                "chunks_to_index": chunk_count,
                "estimated_time_minutes": (doc_count + chunk_count) / 100  # Rough estimate
            }
        else:
            return await backfill_to_elasticsearch()
            
    async def _backfill_highlighting_data(self, dry_run: bool = True) -> Dict[str, Any]:
        """Backfill source highlighting position data"""
        
        # Find chunks missing highlighting data
        missing_highlights = await self.db.execute("""
            SELECT COUNT(*) FROM document_chunks 
            WHERE page_number IS NULL
        """)
        
        count = missing_highlights.scalar()
        
        if dry_run:
            return {
                "chunks_missing_positions": count,
                "estimated_time_minutes": count / 50  # Rough estimate for PDF processing
            }
            
        # Re-process PDFs to extract position information
        if count > 0:
            from src.ingestion.pdf_processor import PDFProcessor
            processor = PDFProcessor()
            
            # Get documents that need reprocessing
            docs_to_process = await self.db.execute("""
                SELECT DISTINCT d.id, d.filename, d.file_type 
                FROM documents d
                JOIN document_chunks dc ON d.id = dc.document_id
                WHERE dc.page_number IS NULL
            """)
            
            processed = 0
            for doc_id, filename, file_type in docs_to_process:
                if file_type == "pdf":
                    try:
                        # Extract position data and update chunks
                        file_path = f"{self.settings.docs_path}/{file_type}/{filename}"
                        position_data = await processor.extract_with_positions(file_path)
                        
                        # Update chunks with position info
                        # (Implementation depends on how chunks map to positions)
                        processed += 1
                        
                    except Exception as e:
                        self.logger.error(f"Failed to process {filename}: {e}")
                        
            return {
                "documents_processed": processed,
                "chunks_updated": count
            }
            
        return {"chunks_missing_positions": 0}
        
    async def _backfill_table_extraction(self, dry_run: bool = True) -> Dict[str, Any]:
        """Backfill table extraction for existing documents"""
        
        # Count documents without table extraction
        docs_without_tables = await self.db.execute("""
            SELECT COUNT(DISTINCT d.id) 
            FROM documents d
            LEFT JOIN extracted_tables et ON d.id = et.document_id
            WHERE et.id IS NULL AND d.file_type = 'pdf'
        """)
        
        count = docs_without_tables.scalar()
        
        if dry_run:
            return {
                "documents_needing_table_extraction": count,
                "estimated_time_minutes": count * 2  # 2 minutes per PDF
            }
            
        # Extract tables from documents
        if count > 0:
            from src.ingestion.table_extractor import TableExtractor
            extractor = TableExtractor(self.settings)
            
            docs_to_process = await self.db.execute("""
                SELECT d.id, d.filename, d.file_type 
                FROM documents d
                LEFT JOIN extracted_tables et ON d.id = et.document_id
                WHERE et.id IS NULL AND d.file_type = 'pdf'
            """)
            
            processed = 0
            tables_extracted = 0
            
            for doc_id, filename, file_type in docs_to_process:
                try:
                    file_path = f"{self.settings.docs_path}/{file_type}/{filename}"
                    tables = await extractor.extract_tables(file_path, file_type)
                    
                    # Store extracted tables
                    for table_data in tables:
                        # Create ExtractedTable entity and save
                        tables_extracted += 1
                        
                    processed += 1
                    
                except Exception as e:
                    self.logger.error(f"Table extraction failed for {filename}: {e}")
                    
            return {
                "documents_processed": processed,
                "tables_extracted": tables_extracted
            }
            
        return {"documents_needing_table_extraction": 0}
```

### 3. Rollout Phases

```python
# scripts/rollout_manager.py
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any
import asyncio

class RolloutPhase(Enum):
    PREPARATION = "preparation"
    BACKFILL = "backfill" 
    CANARY = "canary"
    GRADUAL = "gradual"
    FULL = "full"
    MONITORING = "monitoring"

@dataclass
class RolloutStep:
    phase: RolloutPhase
    name: str
    description: str
    validation_criteria: List[str]
    rollback_enabled: bool = True
    
class RolloutManager:
    """Manages phased rollout of new features"""
    
    ROLLOUT_PLAN = [
        RolloutStep(
            RolloutPhase.PREPARATION,
            "pre_flight_checks",
            "Run pre-rollout validation checks",
            ["All checks pass", "Backups confirmed", "Monitoring active"]
        ),
        RolloutStep(
            RolloutPhase.BACKFILL,
            "data_backfill",
            "Backfill data for new features",
            ["ES indices populated", "Highlight data backfilled", "Tables extracted"],
            rollback_enabled=False  # Backfill is additive
        ),
        RolloutStep(
            RolloutPhase.CANARY,
            "canary_deployment",
            "Enable features for 5% of traffic",
            ["Error rate <1%", "Latency <2x baseline", "No safety alerts"]
        ),
        RolloutStep(
            RolloutPhase.GRADUAL,
            "gradual_rollout", 
            "Increase to 50% traffic",
            ["Error rate <0.5%", "Cache hit rate >20%", "User satisfaction maintained"]
        ),
        RolloutStep(
            RolloutPhase.FULL,
            "full_deployment",
            "Enable for 100% of traffic",
            ["All metrics green", "Performance within SLA", "No critical alerts"]
        ),
        RolloutStep(
            RolloutPhase.MONITORING,
            "post_rollout_monitoring",
            "Monitor for 24 hours",
            ["Stable performance", "No regressions", "Feature adoption measured"]
        )
    ]
    
    def __init__(self, settings, feature_manager):
        self.settings = settings
        self.feature_manager = feature_manager
        self.logger = logging.getLogger(__name__)
        
    async def execute_rollout(self, target_features: List[str]) -> Dict[str, Any]:
        """Execute complete rollout plan"""
        
        results = {}
        current_phase = None
        
        try:
            for step in self.ROLLOUT_PLAN:
                current_phase = step.phase
                self.logger.info(f"Starting rollout step: {step.name}")
                
                # Execute step
                step_result = await self._execute_step(step, target_features)
                results[step.name] = step_result
                
                # Check if step passed
                if not step_result.get("success", False):
                    self.logger.error(f"Step {step.name} failed: {step_result.get('error')}")
                    
                    # Trigger rollback if enabled
                    if step.rollback_enabled:
                        rollback_result = await self._rollback_features(target_features)
                        results["rollback"] = rollback_result
                        
                    break
                    
                self.logger.info(f"Step {step.name} completed successfully")
                
                # Pause between phases for monitoring
                if step.phase != RolloutPhase.MONITORING:
                    await asyncio.sleep(300)  # 5 minute pause
                    
        except Exception as e:
            self.logger.error(f"Rollout failed in phase {current_phase}: {e}")
            
            # Emergency rollback
            rollback_result = await self._rollback_features(target_features)
            results["emergency_rollback"] = rollback_result
            
        return results
        
    async def _execute_step(self, step: RolloutStep, features: List[str]) -> Dict[str, Any]:
        """Execute individual rollout step"""
        
        if step.phase == RolloutPhase.PREPARATION:
            return await self._prepare_rollout()
            
        elif step.phase == RolloutPhase.BACKFILL:
            return await self._execute_backfill()
            
        elif step.phase == RolloutPhase.CANARY:
            return await self._enable_canary(features, traffic_percentage=5)
            
        elif step.phase == RolloutPhase.GRADUAL:
            return await self._enable_gradual(features, traffic_percentage=50)
            
        elif step.phase == RolloutPhase.FULL:
            return await self._enable_full(features)
            
        elif step.phase == RolloutPhase.MONITORING:
            return await self._monitor_post_rollout()
            
    async def _prepare_rollout(self) -> Dict[str, Any]:
        """Preparation phase"""
        checker = PreRolloutChecker(self.settings, self.db, self.redis, self.es_client)
        checks = await checker.run_all_checks()
        
        failures = [c for c in checks if c.status == "fail"]
        
        return {
            "success": len(failures) == 0,
            "checks": [{"name": c.name, "status": c.status, "message": c.message} for c in checks],
            "failures": len(failures)
        }
        
    async def _enable_canary(self, features: List[str], traffic_percentage: int) -> Dict[str, Any]:
        """Enable features for percentage of traffic"""
        
        # Implementation would use feature flags with percentage rollout
        # For now, simulate with time-based enablement
        
        for feature in features:
            await self.feature_manager.set_flag(
                f"enable_{feature}",
                True,
                ttl_minutes=60  # Temporary enablement
            )
            
        # Wait and check metrics
        await asyncio.sleep(300)  # 5 minutes
        
        # Check error rates, latency, etc.
        metrics_ok = await self._check_canary_metrics()
        
        return {
            "success": metrics_ok,
            "traffic_percentage": traffic_percentage,
            "features_enabled": features
        }
        
    async def _check_canary_metrics(self) -> bool:
        """Check if canary metrics are within acceptable bounds"""
        # This would integrate with actual metrics system
        # For now, simulate checks
        
        checks = [
            # Error rate < 1%
            # Latency < 2x baseline  
            # No safety alerts
        ]
        
        return True  # Placeholder
        
    async def _rollback_features(self, features: List[str]) -> Dict[str, Any]:
        """Emergency rollback of features"""
        
        rollback_actions = []
        
        for feature in features:
            try:
                # Disable feature flag
                await self.feature_manager.set_flag(f"enable_{feature}", False)
                rollback_actions.append(f"Disabled {feature}")
                
                # Feature-specific rollback
                if feature == "hybrid_search":
                    # Switch back to pgvector only
                    await self.feature_manager.set_flag("search_backend", "pgvector")
                    rollback_actions.append("Switched to pgvector backend")
                    
                elif feature == "semantic_cache":
                    # Clear cache
                    await self.redis.flushdb()
                    rollback_actions.append("Cleared semantic cache")
                    
            except Exception as e:
                rollback_actions.append(f"Failed to rollback {feature}: {e}")
                
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "actions": rollback_actions
        }
```

### 4. Validation and Testing

```python
# scripts/rollout_validation.py
class RolloutValidator:
    """Validates rollout success at each phase"""
    
    async def validate_canary_phase(self) -> Dict[str, bool]:
        """Validate canary deployment"""
        return {
            "error_rate_acceptable": await self._check_error_rate(threshold=0.01),
            "latency_acceptable": await self._check_latency_increase(max_increase=2.0),
            "no_safety_alerts": await self._check_safety_alerts(),
            "feature_adoption": await self._check_feature_usage()
        }
        
    async def validate_full_deployment(self) -> Dict[str, bool]:
        """Validate full deployment"""
        return {
            "all_systems_healthy": await self._check_system_health(),
            "performance_within_sla": await self._check_performance_sla(),
            "cache_effectiveness": await self._check_cache_metrics(),
            "user_satisfaction": await self._check_response_quality()
        }
        
    async def _check_error_rate(self, threshold: float) -> bool:
        """Check if error rate is below threshold"""
        # Query metrics for error rate over last 15 minutes
        # Return True if below threshold
        return True
        
    async def _check_latency_increase(self, max_increase: float) -> bool:
        """Check if latency increase is acceptable"""
        # Compare current latency to baseline
        # Return True if increase is less than max_increase factor
        return True
        
    async def _check_safety_alerts(self) -> bool:
        """Check for medical safety alerts"""
        # Query safety alert metrics
        # Return True if no critical alerts
        return True
```

### 5. Makefile Integration

```makefile
# Makefile.v8 (rollout commands)
rollout-check:  ## Run pre-rollout validation
	python -m scripts.pre_rollout_checklist

backfill-dry-run:  ## Dry run of data backfill
	python -m scripts.backfill_manager --dry-run

backfill-execute:  ## Execute data backfill
	python -m scripts.backfill_manager --execute

rollout-canary:  ## Start canary rollout
	python -m scripts.rollout_manager --phase canary --features hybrid_search,semantic_cache

rollout-full:  ## Complete full rollout
	python -m scripts.rollout_manager --phase full --features hybrid_search,semantic_cache,table_extraction

rollout-rollback:  ## Emergency rollback
	python -m scripts.rollout_manager --rollback --features all

rollout-status:  ## Check rollout status
	curl http://localhost:8001/api/v1/config/flags | jq '.'
```

## Rollout Timeline

### Phase 1: Preparation (Day 1)
- Run pre-rollout checks
- Execute backfill (dry run first)
- Verify monitoring setup
- Create rollback plan

### Phase 2: Canary (Day 2)
- Enable hybrid search for 5% traffic
- Monitor for 4 hours
- Validate metrics
- Proceed or rollback

### Phase 3: Gradual (Day 2-3)
- Increase to 50% traffic
- Enable additional features
- Monitor overnight
- Validate business metrics

### Phase 4: Full (Day 3)
- Enable for 100% traffic
- Full feature suite active
- Extended monitoring period
- Success metrics collection

## Success Criteria
- Zero critical incidents during rollout
- <5% increase in P95 latency
- >20% cache hit rate achieved
- No medical safety alerts
- Successful rollback test

## Emergency Procedures
1. **Circuit Breaker**: Auto-disable on high error rate
2. **Quick Rollback**: <5 minute feature disable
3. **Data Recovery**: Fallback to pgvector queries
4. **Communication**: Alert stakeholders within 15 minutes

This comprehensive rollout plan ensures safe deployment of the new hybrid search and enhancement features with proper validation, monitoring, and rollback capabilities.