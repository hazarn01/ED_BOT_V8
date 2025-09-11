"""
Health monitoring and system status checks for EDBotv8.

Provides comprehensive health checks for all system components with
scoring, alerting, and integration with metrics collection.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """System component types"""
    DATABASE = "database"
    REDIS = "redis"
    ELASTICSEARCH = "elasticsearch"
    LLM_BACKEND = "llm"
    API = "api"
    METRICS = "metrics"
    CACHE = "cache"
    FEATURE_FLAGS = "feature_flags"


@dataclass
class HealthCheck:
    """Individual health check result"""
    component: ComponentType
    status: HealthStatus
    response_time_ms: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "component": self.component.value,
            "status": self.status.value,
            "response_time_ms": round(self.response_time_ms, 2),
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "is_healthy": self.status == HealthStatus.HEALTHY
        }


@dataclass
class SystemHealth:
    """Overall system health summary"""
    overall_status: HealthStatus
    health_score: float  # 0.0 to 1.0
    component_checks: List[HealthCheck]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "overall_status": self.overall_status.value,
            "health_score": round(self.health_score, 3),
            "timestamp": self.timestamp.isoformat(),
            "components": [check.to_dict() for check in self.component_checks],
            "healthy_components": len([c for c in self.component_checks if c.status == HealthStatus.HEALTHY]),
            "total_components": len(self.component_checks),
            "summary": self._get_summary()
        }
    
    def _get_summary(self) -> Dict[str, int]:
        """Get summary counts by status"""
        summary = {status.value: 0 for status in HealthStatus}
        for check in self.component_checks:
            summary[check.status.value] += 1
        return summary


class HealthMonitor:
    """System health monitoring and checking"""
    
    def __init__(self, settings=None):
        self.settings = settings
        self.enabled = getattr(settings, 'enable_health_monitoring', True) if settings else True
        self.check_interval = getattr(settings, 'health_check_interval', 30) if settings else 30
        self.timeout_seconds = 5.0
        self._last_health_check: Optional[SystemHealth] = None
        self._health_history: List[SystemHealth] = []
        self._max_history = 100
        
        # Component-specific settings
        self.db_host = getattr(settings, 'db_host', 'localhost') if settings else 'localhost'
        self.db_port = getattr(settings, 'db_port', 5432) if settings else 5432
        self.redis_host = getattr(settings, 'redis_host', 'localhost') if settings else 'localhost'
        self.redis_port = getattr(settings, 'redis_port', 6379) if settings else 6379
        
        # Elasticsearch settings
        self.elasticsearch_url = None
        if settings and hasattr(settings, 'hybrid_search'):
            self.elasticsearch_url = getattr(settings.hybrid_search, 'elasticsearch_url', None)
        
        # LLM backend settings
        self.llm_backend = getattr(settings, 'llm_backend', 'ollama') if settings else 'ollama'
        self.ollama_url = getattr(settings, 'ollama_base_url', 'http://localhost:11434') if settings else 'http://localhost:11434'
        self.vllm_url = getattr(settings, 'vllm_base_url', 'http://localhost:8000') if settings else 'http://localhost:8000'
    
    async def check_database_health(self) -> HealthCheck:
        """Check PostgreSQL database health using async connection."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            from sqlalchemy import text

            from ..models.async_database import get_database
            
            async with get_database() as db:
                # Test basic connectivity
                result = await db.execute(text("SELECT 1 as health_check"))
                row = result.fetchone()
                
                response_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                if row and row[0] == 1:
                    # Get additional database health details
                    details = await self._get_async_database_details(db)
                    
                    if response_time > 1000:  # > 1 second is degraded
                        return HealthCheck(
                            ComponentType.DATABASE,
                            HealthStatus.DEGRADED,
                            response_time,
                            f"Database responding slowly ({response_time:.0f}ms)",
                            details
                        )
                    
                    return HealthCheck(
                        ComponentType.DATABASE,
                        HealthStatus.HEALTHY,
                        response_time,
                        "Database connection healthy",
                        details
                    )
                else:
                    return HealthCheck(
                        ComponentType.DATABASE,
                        HealthStatus.UNHEALTHY,
                        response_time,
                        "Database query returned unexpected result"
                    )
                    
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            return HealthCheck(
                ComponentType.DATABASE,
                HealthStatus.UNHEALTHY,
                response_time,
                f"Database connection failed: {str(e)[:100]}"
            )
    
    async def _get_async_database_details(self, db) -> Dict[str, Any]:
        """Get additional database health details using async session."""
        try:
            from sqlalchemy import text
            
            # Check database size and connection info
            size_result = await db.execute(text("""
                SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                       current_database() as name
            """))
            size_row = size_result.fetchone()
            
            # Check active connections
            conn_result = await db.execute(text("""
                SELECT count(*) as active_connections 
                FROM pg_stat_activity 
                WHERE state = 'active'
            """))
            conn_row = conn_result.fetchone()
            
            return {
                "database_size": size_row[0] if size_row else "unknown",
                "database_name": size_row[1] if size_row else "unknown", 
                "active_connections": conn_row[0] if conn_row else 0,
                "version": "PostgreSQL",
                "connection_type": "async"
            }
        except Exception:
            return {"connection_type": "async", "error": "Could not fetch details"}
    
    async def check_redis_health(self) -> HealthCheck:
        """Check Redis cache health"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            import redis.asyncio as redis
            
            client = redis.Redis(
                host=self.redis_host, 
                port=self.redis_port,
                decode_responses=True,
                socket_timeout=self.timeout_seconds
            )
            
            # Test basic operations
            test_key = "health_check"
            test_value = f"health_{datetime.now().timestamp()}"
            
            await client.set(test_key, test_value, ex=10)  # Expire in 10 seconds
            stored_value = await client.get(test_key)
            await client.delete(test_key)
            
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            if stored_value == test_value:
                # Get Redis info
                info = await client.info()
                details = {
                    "version": info.get('redis_version', 'unknown'),
                    "connected_clients": info.get('connected_clients', 0),
                    "used_memory_human": info.get('used_memory_human', 'unknown'),
                    "uptime_in_seconds": info.get('uptime_in_seconds', 0)
                }
                
                if response_time > 500:  # > 500ms is degraded for Redis
                    return HealthCheck(
                        ComponentType.REDIS,
                        HealthStatus.DEGRADED,
                        response_time,
                        f"Redis responding slowly ({response_time:.0f}ms)",
                        details
                    )
                
                return HealthCheck(
                    ComponentType.REDIS,
                    HealthStatus.HEALTHY,
                    response_time,
                    "Redis connection healthy",
                    details
                )
            else:
                return HealthCheck(
                    ComponentType.REDIS,
                    HealthStatus.UNHEALTHY,
                    response_time,
                    "Redis set/get operations failed"
                )
                
            await client.close()
            
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            return HealthCheck(
                ComponentType.REDIS,
                HealthStatus.UNHEALTHY,
                response_time,
                f"Redis connection failed: {str(e)[:100]}"
            )
    
    async def check_elasticsearch_health(self) -> HealthCheck:
        """Check Elasticsearch health"""
        if not self.elasticsearch_url:
            return HealthCheck(
                ComponentType.ELASTICSEARCH,
                HealthStatus.UNKNOWN,
                0.0,
                "Elasticsearch not configured"
            )
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
                async with session.get(f"{self.elasticsearch_url}/_cluster/health") as response:
                    response_time = (asyncio.get_event_loop().time() - start_time) * 1000
                    
                    if response.status == 200:
                        health_data = await response.json()
                        cluster_status = health_data.get('status', 'unknown')
                        
                        details = {
                            "cluster_name": health_data.get('cluster_name', 'unknown'),
                            "status": cluster_status,
                            "active_shards": health_data.get('active_shards', 0),
                            "number_of_nodes": health_data.get('number_of_nodes', 0),
                            "number_of_data_nodes": health_data.get('number_of_data_nodes', 0)
                        }
                        
                        if cluster_status == 'green':
                            status = HealthStatus.HEALTHY
                            message = "Elasticsearch cluster healthy"
                        elif cluster_status == 'yellow':
                            status = HealthStatus.DEGRADED
                            message = "Elasticsearch cluster degraded (yellow status)"
                        else:
                            status = HealthStatus.UNHEALTHY
                            message = f"Elasticsearch cluster unhealthy ({cluster_status})"
                        
                        return HealthCheck(
                            ComponentType.ELASTICSEARCH,
                            status,
                            response_time,
                            message,
                            details
                        )
                    else:
                        return HealthCheck(
                            ComponentType.ELASTICSEARCH,
                            HealthStatus.UNHEALTHY,
                            response_time,
                            f"Elasticsearch returned status {response.status}"
                        )
                        
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            return HealthCheck(
                ComponentType.ELASTICSEARCH,
                HealthStatus.UNHEALTHY,
                response_time,
                f"Elasticsearch connection failed: {str(e)[:100]}"
            )
    
    async def check_llm_backend_health(self) -> HealthCheck:
        """Check LLM backend health"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            if self.llm_backend == 'ollama':
                return await self._check_ollama_health(start_time)
            elif self.llm_backend == 'gpt-oss':
                return await self._check_vllm_health(start_time)
            elif self.llm_backend == 'azure':
                return await self._check_azure_health(start_time)
            else:
                return HealthCheck(
                    ComponentType.LLM_BACKEND,
                    HealthStatus.UNKNOWN,
                    0.0,
                    f"Unknown LLM backend: {self.llm_backend}"
                )
                
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            return HealthCheck(
                ComponentType.LLM_BACKEND,
                HealthStatus.UNHEALTHY,
                response_time,
                f"LLM backend check failed: {str(e)[:100]}"
            )
    
    async def _check_ollama_health(self, start_time: float) -> HealthCheck:
        """Check Ollama health"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
                async with session.get(f"{self.ollama_url}/api/tags") as response:
                    response_time = (asyncio.get_event_loop().time() - start_time) * 1000
                    
                    if response.status == 200:
                        data = await response.json()
                        models = data.get('models', [])
                        
                        details = {
                            "backend_type": "ollama",
                            "available_models": len(models),
                            "models": [model.get('name', '') for model in models[:5]]  # First 5 models
                        }
                        
                        return HealthCheck(
                            ComponentType.LLM_BACKEND,
                            HealthStatus.HEALTHY,
                            response_time,
                            f"Ollama healthy with {len(models)} models",
                            details
                        )
                    else:
                        return HealthCheck(
                            ComponentType.LLM_BACKEND,
                            HealthStatus.UNHEALTHY,
                            response_time,
                            f"Ollama returned status {response.status}"
                        )
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            return HealthCheck(
                ComponentType.LLM_BACKEND,
                HealthStatus.UNHEALTHY,
                response_time,
                f"Ollama connection failed: {str(e)[:100]}"
            )
    
    async def _check_vllm_health(self, start_time: float) -> HealthCheck:
        """Check vLLM health"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
                async with session.get(f"{self.vllm_url}/health") as response:
                    response_time = (asyncio.get_event_loop().time() - start_time) * 1000
                    
                    if response.status == 200:
                        details = {
                            "backend_type": "vllm",
                            "endpoint": self.vllm_url
                        }
                        
                        return HealthCheck(
                            ComponentType.LLM_BACKEND,
                            HealthStatus.HEALTHY,
                            response_time,
                            "vLLM backend healthy",
                            details
                        )
                    else:
                        return HealthCheck(
                            ComponentType.LLM_BACKEND,
                            HealthStatus.UNHEALTHY,
                            response_time,
                            f"vLLM returned status {response.status}"
                        )
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            return HealthCheck(
                ComponentType.LLM_BACKEND,
                HealthStatus.UNHEALTHY,
                response_time,
                f"vLLM connection failed: {str(e)[:100]}"
            )
    
    async def _check_azure_health(self, start_time: float) -> HealthCheck:
        """Check Azure OpenAI health"""
        # For Azure, we'd need API key and endpoint from settings
        # This is a simplified check
        response_time = (asyncio.get_event_loop().time() - start_time) * 1000
        return HealthCheck(
            ComponentType.LLM_BACKEND,
            HealthStatus.UNKNOWN,
            response_time,
            "Azure OpenAI health check not implemented"
        )
    
    async def check_feature_flags_health(self) -> HealthCheck:
        """Check feature flag system health"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            from ..config.feature_manager import FeatureManager
            
            # Create a temporary feature manager to test
            feature_manager = FeatureManager(self.settings)
            
            # Test basic flag access
            await feature_manager.get_flag("enable_metrics")
            
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Get flag statistics
            all_flags = await feature_manager.get_all_flags()
            overrides = sum(1 for flag in all_flags.values() if flag.get('has_override', False))
            
            details = {
                "total_flags": len(all_flags),
                "active_overrides": overrides,
                "redis_connected": True  # If we got this far, Redis is working
            }
            
            return HealthCheck(
                ComponentType.FEATURE_FLAGS,
                HealthStatus.HEALTHY,
                response_time,
                f"Feature flags healthy ({len(all_flags)} flags, {overrides} overrides)",
                details
            )
            
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            return HealthCheck(
                ComponentType.FEATURE_FLAGS,
                HealthStatus.UNHEALTHY,
                response_time,
                f"Feature flags check failed: {str(e)[:100]}"
            )
    
    async def check_metrics_health(self) -> HealthCheck:
        """Check metrics collection health"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Test metrics collection
            from prometheus_client import generate_latest

            from .metrics import metrics
            
            # Try to generate metrics
            metrics_data = generate_latest()
            
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            details = {
                "metrics_enabled": metrics.enabled,
                "metrics_size_bytes": len(metrics_data) if metrics_data else 0
            }
            
            if not metrics.enabled:
                return HealthCheck(
                    ComponentType.METRICS,
                    HealthStatus.DEGRADED,
                    response_time,
                    "Metrics collection disabled",
                    details
                )
            
            return HealthCheck(
                ComponentType.METRICS,
                HealthStatus.HEALTHY,
                response_time,
                "Metrics collection healthy",
                details
            )
            
        except Exception as e:
            response_time = (asyncio.get_event_loop().time() - start_time) * 1000
            return HealthCheck(
                ComponentType.METRICS,
                HealthStatus.UNHEALTHY,
                response_time,
                f"Metrics check failed: {str(e)[:100]}"
            )
    
    async def perform_comprehensive_health_check(self) -> SystemHealth:
        """Perform complete system health check"""
        if not self.enabled:
            return SystemHealth(
                HealthStatus.UNKNOWN,
                0.0,
                [HealthCheck(ComponentType.API, HealthStatus.UNKNOWN, 0.0, "Health monitoring disabled")]
            )
        
        logger.info("Starting comprehensive health check")
        
        # Run all health checks concurrently
        health_checks = await asyncio.gather(
            self.check_database_health(),
            self.check_redis_health(),
            self.check_elasticsearch_health(),
            self.check_llm_backend_health(),
            self.check_feature_flags_health(),
            self.check_metrics_health(),
            return_exceptions=True
        )
        
        # Filter out any exceptions and convert to HealthCheck objects
        valid_checks = []
        for check in health_checks:
            if isinstance(check, HealthCheck):
                valid_checks.append(check)
            elif isinstance(check, Exception):
                # Create error health check
                valid_checks.append(HealthCheck(
                    ComponentType.API,
                    HealthStatus.UNHEALTHY,
                    0.0,
                    f"Health check error: {str(check)[:100]}"
                ))
        
        # Calculate overall health score and status
        health_score = self._calculate_health_score(valid_checks)
        overall_status = self._determine_overall_status(valid_checks)
        
        system_health = SystemHealth(
            overall_status=overall_status,
            health_score=health_score,
            component_checks=valid_checks
        )
        
        # Update metrics if enabled
        await self._update_health_metrics(system_health)
        
        # Store in history
        self._last_health_check = system_health
        self._health_history.append(system_health)
        if len(self._health_history) > self._max_history:
            self._health_history.pop(0)
        
        logger.info(f"Health check complete: {overall_status.value} (score: {health_score:.3f})")
        
        return system_health
    
    def _calculate_health_score(self, checks: List[HealthCheck]) -> float:
        """Calculate overall health score (0.0 to 1.0)"""
        if not checks:
            return 0.0
        
        # Weight by component importance
        weights = {
            ComponentType.DATABASE: 0.25,
            ComponentType.REDIS: 0.15,
            ComponentType.LLM_BACKEND: 0.25,
            ComponentType.ELASTICSEARCH: 0.1,
            ComponentType.FEATURE_FLAGS: 0.1,
            ComponentType.METRICS: 0.05,
            ComponentType.API: 0.1
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for check in checks:
            weight = weights.get(check.component, 0.1)
            
            if check.status == HealthStatus.HEALTHY:
                component_score = 1.0
            elif check.status == HealthStatus.DEGRADED:
                component_score = 0.7
            elif check.status == HealthStatus.UNKNOWN:
                component_score = 0.5
            else:  # UNHEALTHY
                component_score = 0.0
            
            total_score += component_score * weight
            total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _determine_overall_status(self, checks: List[HealthCheck]) -> HealthStatus:
        """Determine overall system status"""
        if not checks:
            return HealthStatus.UNKNOWN
        
        # Critical components (system fails if these are unhealthy)
        critical_components = {ComponentType.DATABASE, ComponentType.LLM_BACKEND}
        
        unhealthy_count = 0
        degraded_count = 0
        critical_unhealthy = False
        
        for check in checks:
            if check.status == HealthStatus.UNHEALTHY:
                unhealthy_count += 1
                if check.component in critical_components:
                    critical_unhealthy = True
            elif check.status == HealthStatus.DEGRADED:
                degraded_count += 1
        
        # If any critical component is unhealthy, system is unhealthy
        if critical_unhealthy:
            return HealthStatus.UNHEALTHY
        
        # If >50% components unhealthy, system is unhealthy  
        if unhealthy_count > len(checks) / 2:
            return HealthStatus.UNHEALTHY
        
        # If any component is degraded or some are unhealthy, system is degraded
        if degraded_count > 0 or unhealthy_count > 0:
            return HealthStatus.DEGRADED
        
        return HealthStatus.HEALTHY
    
    async def _update_health_metrics(self, system_health: SystemHealth):
        """Update Prometheus metrics with health data"""
        try:
            from .metrics import metrics
            
            # Update overall system health
            metrics.update_system_health(system_health.health_score)
            
            # Update individual component health
            for check in system_health.component_checks:
                is_healthy = check.status == HealthStatus.HEALTHY
                metrics.update_component_health(check.component.value, is_healthy)
                
        except Exception as e:
            logger.error(f"Failed to update health metrics: {e}")
    
    def get_last_health_check(self) -> Optional[SystemHealth]:
        """Get the last health check result"""
        return self._last_health_check
    
    def get_health_history(self, limit: int = 10) -> List[SystemHealth]:
        """Get recent health check history"""
        return self._health_history[-limit:] if self._health_history else []
    
    def get_health_trends(self) -> Dict[str, Any]:
        """Get health trends over time"""
        if not self._health_history:
            return {"message": "No health history available"}
        
        # Calculate trends over last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_checks = [
            check for check in self._health_history 
            if check.timestamp >= one_hour_ago
        ]
        
        if len(recent_checks) < 2:
            return {"message": "Insufficient history for trends"}
        
        # Calculate average health score trend
        scores = [check.health_score for check in recent_checks]
        avg_score = sum(scores) / len(scores)
        
        # Calculate component reliability
        component_uptime = {}
        for check in recent_checks:
            for comp_check in check.component_checks:
                component = comp_check.component.value
                if component not in component_uptime:
                    component_uptime[component] = {"healthy": 0, "total": 0}
                
                component_uptime[component]["total"] += 1
                if comp_check.status == HealthStatus.HEALTHY:
                    component_uptime[component]["healthy"] += 1
        
        # Calculate uptime percentages
        uptime_percentages = {}
        for component, stats in component_uptime.items():
            uptime_percentages[component] = (stats["healthy"] / stats["total"]) * 100
        
        return {
            "time_period": "last_hour",
            "checks_count": len(recent_checks),
            "average_health_score": round(avg_score, 3),
            "component_uptime_percent": uptime_percentages,
            "trend": "improving" if scores[-1] > scores[0] else "degrading" if scores[-1] < scores[0] else "stable"
        }


# Global health monitor instance  
health_monitor = HealthMonitor()


def init_health_monitoring(settings):
    """Initialize health monitoring with settings"""
    global health_monitor
    health_monitor = HealthMonitor(settings)
    
    # Start background health check task if enabled
    if health_monitor.enabled:
        import asyncio
        asyncio.create_task(_background_health_monitoring())


async def _background_health_monitoring():
    """Background task for periodic health monitoring"""
    while health_monitor.enabled:
        try:
            await health_monitor.perform_comprehensive_health_check()
            await asyncio.sleep(health_monitor.check_interval)
        except Exception as e:
            logger.error(f"Background health monitoring error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error