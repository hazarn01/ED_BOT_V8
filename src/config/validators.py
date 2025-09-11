"""
Configuration validation for EDBotv8.

Validates configuration consistency, dependencies, and production safety.
Implements a warning/error API expected by tests.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .enhanced_settings import EnhancedSettings

logger = logging.getLogger(__name__)


@dataclass
class ValidationWarning:
    component: str
    message: str
    severity: str = "LOW"
    recommendation: Optional[str] = None


@dataclass
class ValidationError:
    component: str
    message: str
    severity: str = "CRITICAL"
    recommendation: Optional[str] = None


class ConfigurationValidator:
    """Validate configuration consistency and safety"""
    
    def __init__(self, settings: EnhancedSettings):
        if settings is None:
            raise ValueError("settings must not be None")
        self.settings = settings
        self.warnings: List[ValidationWarning] = []
        self.errors: List[ValidationError] = []
    
    # --- Public API used in tests ---
    def validate_all(self) -> List[ValidationWarning]:
        """Run all configuration validations and return warnings list.
        Errors are also stored on self.errors.
        """
        self._clear_results()
        try:
            self._validate_app_name()
            self._validate_environment()
            self._validate_llm_backend()
            self._validate_feature_flag_consistency()
            self._validate_feature_dependencies()
            self._validate_production_safety()
            self._validate_hybrid_search_config()
            self._validate_performance_settings()
            self._validate_resource_limits()
            self._validate_security_settings()
        except Exception as e:
            self._add_warning("validator", f"Validation error: {e}", "LOW")
            logger.error(f"Configuration validation failed: {e}")
        return self.warnings
        
    # --- Individual validators (kept concise, tailored to tests) ---
    def _validate_app_name(self):
        try:
            name = getattr(self.settings, "app_name", None)
            if not name:
                self._add_warning("app_name", "app_name is empty", "MEDIUM")
        except Exception as e:
            self._add_error("app_name", f"app_name validation failed: {e}")
    
    def _validate_environment(self):
        env = getattr(self.settings, "environment", "").lower()
        if env not in {"development", "staging", "production", "test"}:
            self._add_warning("environment", f"Invalid environment: {env}", "LOW")
    
    def _validate_llm_backend(self):
        backend = getattr(self.settings, "llm_backend", "")
        valids = {"gpt-oss", "ollama", "azure"}
        if backend not in valids:
            self._add_warning("llm", f"Unsupported llm backend: {backend}", "LOW")
    
    def _validate_feature_flag_consistency(self):
        features = self.settings.features
        if getattr(features, "search_backend", "") == "hybrid" and not getattr(features, "enable_hybrid_search", False):
            self._add_warning("features", "Hybrid backend selected but enable_hybrid_search is False", "MEDIUM")
    
    def _validate_production_safety(self):
        if getattr(self.settings, "is_production", False):
            features = self.settings.features
            if not getattr(features, "enable_phi_scrubbing", False):
                self._add_error("safety", "PHI scrubbing disabled in production", "CRITICAL")
            if not getattr(features, "enable_response_validation", False):
                self._add_warning("safety", "Response validation disabled in production", "HIGH")
            if getattr(features, "enable_streamlit_demo", False) or getattr(features, "enable_pdf_viewer", False):
                self._add_warning("environment", "Development UI features enabled in production", "MEDIUM")
        else:
            # Experimental features allowed in development; warn softly if flagged
            if getattr(self.settings.features, "enable_streamlit_demo", False):
                self._add_warning("environment", "Experimental feature enabled (development)", "LOW")
    
    def _validate_feature_dependencies(self):
        features = self.settings.features
        if getattr(features, "enable_hybrid_search", False) and not getattr(features, "enable_elasticsearch", False):
            self._add_warning("features", "Hybrid search enabled but Elasticsearch disabled", "MEDIUM")
        if getattr(features, "enable_semantic_cache", False) and not getattr(self.settings, "redis_host", ""):
            self._add_warning("cache", "Semantic cache enabled but no Redis host configured", "LOW")
    
    def _validate_hybrid_search_config(self):
        hs = getattr(self.settings, "hybrid_search", None)
        if not hs:
            return
        # URL
        url = getattr(hs, "elasticsearch_url", "")
        if url and not self._is_valid_url(url):
            self._add_warning("hybrid_search", f"Invalid Elasticsearch URL format: {url}", "LOW")
        # Weights (if provided as combined fields)
        kw = getattr(hs, "keyword_weight", None)
        sw = getattr(hs, "semantic_weight", None)
        if kw is not None and sw is not None:
            if abs((kw + sw) - 1.0) > 0.01:
                self._add_error("hybrid_search", f"Search weights do not sum to 1.0: {kw}+{sw}", "HIGH")
    
    def _validate_performance_settings(self):
        obs = getattr(self.settings, "observability", None)
        if not obs:
            return
        # Port range check
        port = getattr(obs, "metrics_port", 0)
        if self._is_privileged_port(port):
            self._add_warning("observability", f"Metrics port in privileged range: {port}", "LOW")
        # Performance alert thresholds
        thresh = getattr(obs, "performance_alert_threshold", 2.0)
        if thresh < 0.2:
            self._add_warning("observability", f"Performance alert threshold too low: {thresh}", "LOW")
        if thresh > 20.0:
            self._add_warning("observability", f"Performance alert threshold high: {thresh}", "LOW")
        # Health check interval
        interval = getattr(obs, "health_check_interval", 30)
        if interval < 5:
            self._add_warning("observability", "Health checks too frequent (performance impact)", "LOW")
        
    def _validate_resource_limits(self):
        # Example: table extraction sizing
        if getattr(self.settings.features, "enable_table_extraction", False):
            max_size = getattr(self.settings.table_extraction, "max_table_size", 1000)
            if max_size > 10000:
                self._add_warning("resources", f"Very large max_table_size: {max_size}", "LOW")
            if max_size < 1:
                self._add_warning("resources", f"max_table_size must be >= 1: {max_size}", "LOW")
        
    def _validate_security_settings(self):
        # DB password check (best-effort)
        try:
            db_url = getattr(self.settings, "database_url", "") or ""
            if "password" in db_url.lower() and getattr(self.settings, "db_password", "edbot") == "edbot" and getattr(self.settings, "db_host", "localhost") != "localhost":
                self._add_warning("security", "Default database password used with non-localhost connection", "HIGH")
        except Exception:
            pass
        # Redis DB safety
        if getattr(self.settings, "redis_host", "localhost") != "localhost" and getattr(self.settings, "redis_db", 0) == 0:
            self._add_warning("security", "Using default Redis DB (0) on remote host", "LOW")
        # Docs path traversal
        if ".." in getattr(self.settings, "docs_path", ""):
            self._add_warning("security", "Docs path contains '..'", "LOW")
        
    # --- Helpers expected by tests ---
    def _is_valid_url(self, url: str) -> bool:
        if not url:
            return False
        return bool(re.match(r"^https?://[\w.-]+(?::\d+)?(?:/.*)?$", url))
    
    def _is_privileged_port(self, port: int) -> bool:
        try:
            return int(port) < 1024
        except Exception:
            return False
    
    def _get_enabled_features(self) -> List[str]:
        features = []
        for k, v in getattr(self.settings, "features").__dict__.items():
            if v:
                features.append(k)
        return features
    
    def _get_backend_services(self) -> Dict[str, Any]:
        return {
            "llm": getattr(self.settings, "llm_backend", None),
            "search": getattr(getattr(self.settings, "features"), "search_backend", None)
        }
    
    def _get_recommendation(self, item: Any) -> str:
        msg = (item.message or "").lower()
        if "phi" in msg:
            return "Enable PHI scrubbing and response validation in production"
        if "hybrid" in msg and "elasticsearch" in msg:
            return "Enable Elasticsearch or switch search_backend to pgvector"
        if "port" in msg:
            return "Use an unprivileged port (>=1024) for metrics"
        if "url" in msg:
            return "Set a valid http(s) URL"
        return "Review configuration and align with environment best practices"
        
    # --- Internal helpers to store results ---
    def _add_warning(self, component: str, message: str, severity: str = "LOW"):
        w = ValidationWarning(component=component, message=message, severity=severity)
        w.recommendation = self._get_recommendation(w)
        self.warnings.append(w)
        logger.warning(f"Config warning [{component}]: {message}")
    
    def _add_error(self, component: str, message: str, severity: str = "CRITICAL"):
        e = ValidationError(component=component, message=message, severity=severity)
        e.recommendation = self._get_recommendation(e)
        self.errors.append(e)
        logger.error(f"Config error [{component}]: {message}")
    
    def _clear_results(self):
        self.warnings = []
        self.errors = []
        
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get human-readable configuration summary"""
        summary = {
            "environment": self.settings.environment,
            "enabled_features": [],
            "configuration_warnings": self.validate_all(),
            "backend_services": {
                "database": f"{self.settings.db_host}:{self.settings.db_port}",
                "redis": f"{self.settings.redis_host}:{self.settings.redis_port}",
                "llm": self.settings.llm_backend
            }
        }
        
        # List enabled features
        for field_name, field in self.settings.features.__fields__.items():
            if getattr(self.settings.features, field_name):
                summary["enabled_features"].append(field_name)
                
        # Add conditional backends
        if self.settings.features.enable_elasticsearch:
            summary["backend_services"]["elasticsearch"] = self.settings.hybrid_search.elasticsearch_url
            
        return summary


def validate_configuration(settings: EnhancedSettings) -> List[str]:
    """Convenience function for configuration validation"""
    validator = ConfigurationValidator(settings)
    return validator.validate_all()
