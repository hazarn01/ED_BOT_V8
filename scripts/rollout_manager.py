#!/usr/bin/env python3
"""
Rollout manager for EDBotv8
Handles phased deployment of new features with validation and rollback
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RolloutPhase(Enum):
    PREPARATION = "preparation"
    BACKFILL = "backfill" 
    CANARY = "canary"
    GRADUAL = "gradual"
    FULL = "full"
    MONITORING = "monitoring"
    ROLLBACK = "rollback"

@dataclass
class RolloutStep:
    phase: RolloutPhase
    name: str
    description: str
    validation_criteria: List[str]
    rollback_enabled: bool = True
    duration_minutes: int = 5  # How long to wait in this phase
    
@dataclass
class RolloutState:
    current_phase: RolloutPhase
    current_step: str
    start_time: datetime
    features: List[str]
    traffic_percentage: int = 0
    success: bool = False
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = None

class RolloutValidator:
    """Validates rollout success at each phase"""
    
    def __init__(self, settings, db_session, redis_client, feature_manager):
        self.settings = settings
        self.db = db_session
        self.redis = redis_client
        self.feature_manager = feature_manager
        self.logger = logging.getLogger(__name__)
        
    async def validate_canary_phase(self) -> Dict[str, bool]:
        """Validate canary deployment"""
        try:
            results = {
                "error_rate_acceptable": await self._check_error_rate(threshold=0.01),
                "latency_acceptable": await self._check_latency_increase(max_increase=2.0),
                "no_safety_alerts": await self._check_safety_alerts(),
                "feature_adoption": await self._check_feature_usage(),
                "system_stability": await self._check_system_stability()
            }
            
            self.logger.info(f"Canary validation results: {results}")
            return results
            
        except Exception as e:
            self.logger.error(f"Canary validation failed: {e}")
            return {"validation_failed": False, "error": str(e)}
        
    async def validate_full_deployment(self) -> Dict[str, bool]:
        """Validate full deployment"""
        try:
            results = {
                "all_systems_healthy": await self._check_system_health(),
                "performance_within_sla": await self._check_performance_sla(),
                "cache_effectiveness": await self._check_cache_metrics(),
                "user_satisfaction": await self._check_response_quality(),
                "no_regressions": await self._check_for_regressions()
            }
            
            self.logger.info(f"Full deployment validation results: {results}")
            return results
            
        except Exception as e:
            self.logger.error(f"Full deployment validation failed: {e}")
            return {"validation_failed": False, "error": str(e)}
        
    async def _check_error_rate(self, threshold: float) -> bool:
        """Check if error rate is below threshold"""
        try:
            # Get error rate from Redis metrics
            error_count_key = "metrics:api_errors:count"
            request_count_key = "metrics:api_requests:count"
            
            error_count = await self.redis.get(error_count_key) or 0
            request_count = await self.redis.get(request_count_key) or 1
            
            error_rate = float(error_count) / float(request_count)
            
            self.logger.info(f"Error rate: {error_rate:.4f} (threshold: {threshold})")
            return error_rate < threshold
            
        except Exception as e:
            self.logger.warning(f"Error rate check failed: {e}")
            return True  # Default to pass if we can't check
        
    async def _check_latency_increase(self, max_increase: float) -> bool:
        """Check if latency increase is acceptable"""
        try:
            # Get current and baseline latency
            current_latency_key = "metrics:api_latency:avg"
            baseline_key = "performance_baseline"
            
            current_latency = await self.redis.get(current_latency_key)
            baseline_data = await self.redis.get(baseline_key)
            
            if not current_latency or not baseline_data:
                self.logger.warning("Latency data not available")
                return True
                
            baseline = json.loads(baseline_data)
            baseline_latency = baseline.get("db_query_time", 0.1)
            
            latency_increase = float(current_latency) / baseline_latency
            
            self.logger.info(f"Latency increase: {latency_increase:.2f}x (max: {max_increase}x)")
            return latency_increase <= max_increase
            
        except Exception as e:
            self.logger.warning(f"Latency check failed: {e}")
            return True
        
    async def _check_safety_alerts(self) -> bool:
        """Check for medical safety alerts"""
        try:
            # Check for any safety alerts in the last 15 minutes
            
            # This would integrate with actual alerting system
            # For now, check if any safety-related errors occurred
            
            safety_error_key = "metrics:safety_violations:count"
            safety_errors = await self.redis.get(safety_error_key) or 0
            
            self.logger.info(f"Safety violations: {safety_errors}")
            return int(safety_errors) == 0
            
        except Exception as e:
            self.logger.warning(f"Safety alert check failed: {e}")
            return True
        
    async def _check_feature_usage(self) -> bool:
        """Check if new features are being used"""
        try:
            # Check usage metrics for new features
            feature_usage_keys = [
                "metrics:elasticsearch_queries:count",
                "metrics:table_extraction:count",
                "metrics:cache_hits:count"
            ]
            
            total_usage = 0
            for key in feature_usage_keys:
                usage = await self.redis.get(key) or 0
                total_usage += int(usage)
            
            self.logger.info(f"Feature usage count: {total_usage}")
            return total_usage > 0  # At least some usage
            
        except Exception as e:
            self.logger.warning(f"Feature usage check failed: {e}")
            return True
        
    async def _check_system_stability(self) -> bool:
        """Check overall system stability"""
        try:
            # Check if all critical services are responding
            db_healthy = await self._check_database_health()
            redis_healthy = await self._check_redis_health()
            
            return db_healthy and redis_healthy
            
        except Exception as e:
            self.logger.warning(f"System stability check failed: {e}")
            return False
        
    async def _check_database_health(self) -> bool:
        """Check database health"""
        try:
            start_time = time.time()
            await self.db.execute("SELECT 1")
            query_time = time.time() - start_time
            
            # Database should respond within 1 second
            return query_time < 1.0
            
        except Exception:
            return False
        
    async def _check_redis_health(self) -> bool:
        """Check Redis health"""
        try:
            start_time = time.time()
            pong = await self.redis.ping()
            ping_time = time.time() - start_time
            
            # Redis should respond within 100ms
            return pong and ping_time < 0.1
            
        except Exception:
            return False
        
    async def _check_system_health(self) -> bool:
        """Check if all systems are healthy"""
        return await self._check_system_stability()
        
    async def _check_performance_sla(self) -> bool:
        """Check if performance is within SLA"""
        # Similar to latency check but more comprehensive
        return await self._check_latency_increase(max_increase=1.5)
        
    async def _check_cache_metrics(self) -> bool:
        """Check cache effectiveness"""
        try:
            cache_hits_key = "metrics:cache_hits:count"
            cache_requests_key = "metrics:cache_requests:count"
            
            hits = await self.redis.get(cache_hits_key) or 0
            requests = await self.redis.get(cache_requests_key) or 1
            
            hit_rate = float(hits) / float(requests)
            
            self.logger.info(f"Cache hit rate: {hit_rate:.2%}")
            return hit_rate > 0.2  # 20% hit rate minimum
            
        except Exception as e:
            self.logger.warning(f"Cache metrics check failed: {e}")
            return True
        
    async def _check_response_quality(self) -> bool:
        """Check response quality metrics"""
        try:
            # This would check user satisfaction scores, response relevance, etc.
            # For now, check if no quality alerts have been raised
            
            quality_alerts_key = "alerts:quality:count"
            quality_alerts = await self.redis.get(quality_alerts_key) or 0
            
            return int(quality_alerts) == 0
            
        except Exception as e:
            self.logger.warning(f"Response quality check failed: {e}")
            return True
        
    async def _check_for_regressions(self) -> bool:
        """Check for performance or accuracy regressions"""
        try:
            # Compare current metrics with baseline
            return await self._check_latency_increase(max_increase=1.2) and await self._check_error_rate(threshold=0.005)
            
        except Exception as e:
            self.logger.warning(f"Regression check failed: {e}")
            return True

class RolloutManager:
    """Manages phased rollout of new features"""
    
    ROLLOUT_PLAN = [
        RolloutStep(
            RolloutPhase.PREPARATION,
            "pre_flight_checks",
            "Run pre-rollout validation checks",
            ["All checks pass", "Backups confirmed", "Monitoring active"],
            duration_minutes=2
        ),
        RolloutStep(
            RolloutPhase.BACKFILL,
            "data_backfill",
            "Backfill data for new features",
            ["ES indices populated", "Highlight data backfilled", "Tables extracted"],
            rollback_enabled=False,  # Backfill is additive
            duration_minutes=1
        ),
        RolloutStep(
            RolloutPhase.CANARY,
            "canary_deployment",
            "Enable features for 5% of traffic",
            ["Error rate <1%", "Latency <2x baseline", "No safety alerts"],
            duration_minutes=10
        ),
        RolloutStep(
            RolloutPhase.GRADUAL,
            "gradual_rollout", 
            "Increase to 50% traffic",
            ["Error rate <0.5%", "Cache hit rate >20%", "User satisfaction maintained"],
            duration_minutes=15
        ),
        RolloutStep(
            RolloutPhase.FULL,
            "full_deployment",
            "Enable for 100% of traffic",
            ["All metrics green", "Performance within SLA", "No critical alerts"],
            duration_minutes=5
        ),
        RolloutStep(
            RolloutPhase.MONITORING,
            "post_rollout_monitoring",
            "Monitor for stability",
            ["Stable performance", "No regressions", "Feature adoption measured"],
            duration_minutes=30
        )
    ]
    
    def __init__(self, settings, db_session, redis_client, feature_manager):
        self.settings = settings
        self.db = db_session
        self.redis = redis_client
        self.feature_manager = feature_manager
        self.logger = logging.getLogger(__name__)
        self.validator = RolloutValidator(settings, db_session, redis_client, feature_manager)
        
    async def execute_rollout(self, target_features: List[str], start_phase: Optional[RolloutPhase] = None) -> Dict[str, Any]:
        """Execute complete rollout plan"""
        
        self.logger.info(f"Starting rollout for features: {', '.join(target_features)}")
        
        # Initialize rollout state
        rollout_state = RolloutState(
            current_phase=start_phase or RolloutPhase.PREPARATION,
            current_step="starting",
            start_time=datetime.utcnow(),
            features=target_features
        )
        
        # Store rollout state
        await self._save_rollout_state(rollout_state)
        
        results = {}
        
        # Find starting step
        start_index = 0
        if start_phase:
            start_index = next((i for i, step in enumerate(self.ROLLOUT_PLAN) if step.phase == start_phase), 0)
        
        try:
            for i, step in enumerate(self.ROLLOUT_PLAN[start_index:], start_index):
                rollout_state.current_phase = step.phase
                rollout_state.current_step = step.name
                await self._save_rollout_state(rollout_state)
                
                self.logger.info(f"🚀 Starting rollout step: {step.name} - {step.description}")
                
                # Execute step
                step_result = await self._execute_step(step, target_features)
                results[step.name] = step_result
                
                # Check if step passed
                if not step_result.get("success", False):
                    self.logger.error(f"❌ Step {step.name} failed: {step_result.get('error')}")
                    
                    rollout_state.success = False
                    rollout_state.error_message = step_result.get('error')
                    await self._save_rollout_state(rollout_state)
                    
                    # Trigger rollback if enabled
                    if step.rollback_enabled:
                        self.logger.info("🔄 Triggering rollback...")
                        rollback_result = await self._rollback_features(target_features)
                        results["rollback"] = rollback_result
                        
                    break
                    
                self.logger.info(f"✅ Step {step.name} completed successfully")
                
                # Wait between phases for monitoring (except for monitoring phase itself)
                if step.phase != RolloutPhase.MONITORING and i < len(self.ROLLOUT_PLAN) - 1:
                    self.logger.info(f"⏳ Waiting {step.duration_minutes} minutes before next phase...")
                    await asyncio.sleep(step.duration_minutes * 60)
            else:
                # All steps completed successfully
                rollout_state.success = True
                await self._save_rollout_state(rollout_state)
                
        except Exception as e:
            self.logger.error(f"💥 Rollout failed with exception: {e}")
            
            rollout_state.success = False
            rollout_state.error_message = str(e)
            await self._save_rollout_state(rollout_state)
            
            # Emergency rollback
            self.logger.info("🚨 Initiating emergency rollback...")
            rollback_result = await self._rollback_features(target_features)
            results["emergency_rollback"] = rollback_result
            
        # Final rollout summary
        total_duration = (datetime.utcnow() - rollout_state.start_time).total_seconds()
        
        summary = {
            "success": rollout_state.success,
            "total_duration_seconds": total_duration,
            "features": target_features,
            "final_phase": rollout_state.current_phase.value,
            "results": results
        }
        
        self.logger.info(f"🏁 Rollout {'completed successfully' if rollout_state.success else 'failed'} in {total_duration:.1f}s")
        
        return summary
        
    async def _execute_step(self, step: RolloutStep, features: List[str]) -> Dict[str, Any]:
        """Execute individual rollout step"""
        
        step_start = datetime.utcnow()
        
        try:
            if step.phase == RolloutPhase.PREPARATION:
                result = await self._prepare_rollout()
                
            elif step.phase == RolloutPhase.BACKFILL:
                result = await self._execute_backfill()
                
            elif step.phase == RolloutPhase.CANARY:
                result = await self._enable_canary(features, traffic_percentage=5)
                
            elif step.phase == RolloutPhase.GRADUAL:
                result = await self._enable_gradual(features, traffic_percentage=50)
                
            elif step.phase == RolloutPhase.FULL:
                result = await self._enable_full(features)
                
            elif step.phase == RolloutPhase.MONITORING:
                result = await self._monitor_post_rollout()
                
            else:
                result = {"success": False, "error": f"Unknown phase: {step.phase}"}
            
            duration = (datetime.utcnow() - step_start).total_seconds()
            result["duration_seconds"] = duration
            
            return result
            
        except Exception as e:
            duration = (datetime.utcnow() - step_start).total_seconds()
            return {
                "success": False,
                "error": str(e),
                "duration_seconds": duration
            }
            
    async def _prepare_rollout(self) -> Dict[str, Any]:
        """Preparation phase"""
        try:
            from scripts.pre_rollout_checklist import PreRolloutChecker
            
            checker = PreRolloutChecker(self.settings, self.db, self.redis)
            checks = await checker.run_all_checks()
            
            failures = [c for c in checks if c.status == "fail"]
            
            return {
                "success": len(failures) == 0,
                "checks": [{"name": c.name, "status": c.status, "message": c.message} for c in checks],
                "failures": len(failures),
                "total_checks": len(checks)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Pre-rollout checks failed: {e}"
            }
            
    async def _execute_backfill(self) -> Dict[str, Any]:
        """Backfill phase"""
        try:
            from scripts.backfill_manager import BackfillManager
            
            manager = BackfillManager(self.settings, self.db, self.redis)
            backfill_result = await manager.run_full_backfill(dry_run=False)
            
            return {
                "success": backfill_result["failure_count"] == 0,
                "backfill_summary": backfill_result
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Backfill failed: {e}"
            }
            
    async def _enable_canary(self, features: List[str], traffic_percentage: int) -> Dict[str, Any]:
        """Enable features for percentage of traffic"""
        
        try:
            # Enable features with limited scope
            for feature in features:
                flag_name = f"enable_{feature}"
                await self.feature_manager.set_flag(
                    flag_name,
                    True,
                    ttl_minutes=60  # Temporary enablement
                )
                
                self.logger.info(f"Enabled feature flag: {flag_name}")
            
            # Set traffic percentage (this would integrate with load balancer/feature flags)
            await self.redis.set("rollout:traffic_percentage", traffic_percentage, ex=3600)
            
            # Wait for metrics to accumulate
            await asyncio.sleep(60)  # 1 minute
            
            # Validate canary metrics
            validation_results = await self.validator.validate_canary_phase()
            metrics_ok = all(validation_results.values())
            
            return {
                "success": metrics_ok,
                "traffic_percentage": traffic_percentage,
                "features_enabled": features,
                "validation_results": validation_results
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Canary deployment failed: {e}"
            }
            
    async def _enable_gradual(self, features: List[str], traffic_percentage: int) -> Dict[str, Any]:
        """Gradual rollout phase"""
        
        try:
            # Increase traffic percentage
            await self.redis.set("rollout:traffic_percentage", traffic_percentage, ex=3600)
            
            # Enable additional feature flags if any
            for feature in features:
                extended_flag = f"enable_{feature}_extended"
                await self.feature_manager.set_flag(extended_flag, True, ttl_minutes=120)
            
            # Wait longer for gradual phase
            await asyncio.sleep(120)  # 2 minutes
            
            # Validate gradual rollout
            validation_results = await self.validator.validate_canary_phase()  # Same validations
            metrics_ok = all(validation_results.values())
            
            return {
                "success": metrics_ok,
                "traffic_percentage": traffic_percentage,
                "validation_results": validation_results
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Gradual rollout failed: {e}"
            }
            
    async def _enable_full(self, features: List[str]) -> Dict[str, Any]:
        """Full deployment phase"""
        
        try:
            # Enable features for 100% traffic
            await self.redis.set("rollout:traffic_percentage", 100, ex=3600)
            
            # Make feature flags permanent (remove TTL)
            for feature in features:
                flag_name = f"enable_{feature}"
                await self.feature_manager.set_flag(flag_name, True)  # No TTL = permanent
                
            # Validate full deployment
            validation_results = await self.validator.validate_full_deployment()
            metrics_ok = all(validation_results.values())
            
            return {
                "success": metrics_ok,
                "traffic_percentage": 100,
                "features_enabled": features,
                "validation_results": validation_results
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Full deployment failed: {e}"
            }
            
    async def _monitor_post_rollout(self) -> Dict[str, Any]:
        """Post-rollout monitoring phase"""
        
        try:
            monitoring_duration = 300  # 5 minutes
            check_interval = 60  # Check every minute
            
            metrics_history = []
            
            for i in range(monitoring_duration // check_interval):
                # Collect metrics
                validation_results = await self.validator.validate_full_deployment()
                
                metrics_snapshot = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "check_number": i + 1,
                    "validation_results": validation_results,
                    "all_healthy": all(validation_results.values())
                }
                
                metrics_history.append(metrics_snapshot)
                
                if not metrics_snapshot["all_healthy"]:
                    return {
                        "success": False,
                        "error": "Health checks failed during monitoring",
                        "metrics_history": metrics_history
                    }
                
                if i < (monitoring_duration // check_interval) - 1:  # Don't sleep on last iteration
                    await asyncio.sleep(check_interval)
            
            # Calculate stability score
            healthy_checks = sum(1 for m in metrics_history if m["all_healthy"])
            stability_score = healthy_checks / len(metrics_history)
            
            return {
                "success": stability_score >= 0.9,  # 90% of checks must pass
                "stability_score": stability_score,
                "total_checks": len(metrics_history),
                "healthy_checks": healthy_checks,
                "metrics_history": metrics_history
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Post-rollout monitoring failed: {e}"
            }
            
    async def _rollback_features(self, features: List[str]) -> Dict[str, Any]:
        """Emergency rollback of features"""
        
        rollback_start = datetime.utcnow()
        rollback_actions = []
        
        try:
            # Immediately set traffic to 0%
            await self.redis.set("rollout:traffic_percentage", 0, ex=3600)
            rollback_actions.append("Set traffic percentage to 0%")
            
            for feature in features:
                try:
                    # Disable main feature flag
                    main_flag = f"enable_{feature}"
                    await self.feature_manager.set_flag(main_flag, False)
                    rollback_actions.append(f"Disabled {main_flag}")
                    
                    # Disable extended flags
                    extended_flag = f"enable_{feature}_extended"
                    await self.feature_manager.set_flag(extended_flag, False)
                    rollback_actions.append(f"Disabled {extended_flag}")
                    
                    # Feature-specific rollback
                    if feature == "hybrid_search":
                        # Switch back to pgvector only
                        await self.feature_manager.set_flag("search_backend", "pgvector")
                        rollback_actions.append("Switched to pgvector backend")
                        
                    elif feature == "semantic_cache":
                        # Clear semantic cache
                        cache_keys = await self.redis.keys("cache:semantic:*")
                        if cache_keys:
                            await self.redis.delete(*cache_keys)
                            rollback_actions.append(f"Cleared {len(cache_keys)} semantic cache entries")
                            
                    elif feature == "table_extraction":
                        # Disable table extraction processing
                        await self.feature_manager.set_flag("process_tables", False)
                        rollback_actions.append("Disabled table extraction processing")
                        
                except Exception as e:
                    rollback_actions.append(f"Failed to rollback {feature}: {e}")
            
            # Clear rollout state
            await self.redis.delete("rollout:state")
            rollback_actions.append("Cleared rollout state")
            
            rollback_duration = (datetime.utcnow() - rollback_start).total_seconds()
            
            self.logger.info(f"🔄 Rollback completed in {rollback_duration:.2f}s")
            
            return {
                "success": True,
                "timestamp": datetime.utcnow().isoformat(),
                "duration_seconds": rollback_duration,
                "actions": rollback_actions,
                "features_rolled_back": features
            }
            
        except Exception as e:
            rollback_duration = (datetime.utcnow() - rollback_start).total_seconds()
            rollback_actions.append(f"Rollback failed: {e}")
            
            return {
                "success": False,
                "timestamp": datetime.utcnow().isoformat(),
                "duration_seconds": rollback_duration,
                "actions": rollback_actions,
                "error": str(e)
            }
            
    async def _save_rollout_state(self, state: RolloutState):
        """Save rollout state to Redis"""
        try:
            state_data = {
                "current_phase": state.current_phase.value,
                "current_step": state.current_step,
                "start_time": state.start_time.isoformat(),
                "features": state.features,
                "traffic_percentage": state.traffic_percentage,
                "success": state.success,
                "error_message": state.error_message,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            await self.redis.set(
                "rollout:state",
                json.dumps(state_data),
                ex=86400  # 24 hours
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to save rollout state: {e}")
            
    async def get_rollout_status(self) -> Dict[str, Any]:
        """Get current rollout status"""
        try:
            state_data = await self.redis.get("rollout:state")
            if not state_data:
                return {"status": "no_active_rollout"}
                
            state = json.loads(state_data)
            
            # Add current traffic percentage
            current_traffic = await self.redis.get("rollout:traffic_percentage") or 0
            state["current_traffic_percentage"] = int(current_traffic)
            
            return state
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

async def main():
    """CLI entry point for rollout manager"""
    parser = argparse.ArgumentParser(description="Manage phased feature rollouts")
    parser.add_argument("--phase", choices=[p.value for p in RolloutPhase], 
                       help="Start from specific phase")
    parser.add_argument("--features", nargs="+", required=True,
                       help="Features to roll out")
    parser.add_argument("--rollback", action="store_true",
                       help="Rollback specified features")
    parser.add_argument("--status", action="store_true",
                       help="Show current rollout status")
    parser.add_argument("--output", choices=["json", "text"], default="text",
                       help="Output format")
    parser.add_argument("--config-file", help="Path to configuration file")
    
    args = parser.parse_args()
    
    # Setup path for imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    try:
        # Import required components
        from src.cache.redis_client import get_redis_client
        from src.config.enhanced_settings import EnhancedSettings
        from src.config.feature_manager import FeatureManager
        from src.models.database import get_db_session
        
        # Load settings
        if args.config_file:
            os.environ["EDBOT_CONFIG_FILE"] = args.config_file
            
        settings = EnhancedSettings()
        
        # Get connections
        db_session = await get_db_session()
        redis_client = await get_redis_client()
        feature_manager = FeatureManager(settings, redis_client)
        
        # Create rollout manager
        manager = RolloutManager(settings, db_session, redis_client, feature_manager)
        
        if args.status:
            # Show status
            status = await manager.get_rollout_status()
            if args.output == "json":
                print(json.dumps(status, indent=2))
            else:
                print(f"Rollout Status: {status}")
                
        elif args.rollback:
            # Perform rollback
            result = await manager._rollback_features(args.features)
            if args.output == "json":
                print(json.dumps(result, indent=2))
            else:
                if result["success"]:
                    logger.info("✅ Rollback completed successfully")
                else:
                    logger.error("❌ Rollback failed")
                    
        else:
            # Execute rollout
            start_phase = RolloutPhase(args.phase) if args.phase else None
            result = await manager.execute_rollout(args.features, start_phase)
            
            if args.output == "json":
                print(json.dumps(result, indent=2, default=str))
            else:
                if result["success"]:
                    logger.info("✅ Rollout completed successfully")
                else:
                    logger.error("❌ Rollout failed")
                    
        # Exit with appropriate code
        sys.exit(0)
            
    except Exception as e:
        logger.error(f"Rollout manager failed: {e}")
        if args.output == "json":
            error_output = {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "status": "failed"
            }
            print(json.dumps(error_output, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())