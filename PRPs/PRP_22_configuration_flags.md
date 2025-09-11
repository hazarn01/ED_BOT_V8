# PRP 22: Configuration and Feature Flags

## Problem Statement
The new hybrid search and enhancement features need comprehensive configuration management to enable safe rollout, A/B testing, and quick rollback. Feature flags should provide granular control with conservative defaults to ensure production stability.

## Success Criteria
- All new features gated behind feature flags with safe defaults
- Environment-specific configuration support
- Runtime flag updates without restart (where safe)
- Clear documentation for each feature flag
- Migration path from current settings

## Implementation Approach

### 1. Enhanced Settings Structure
```python
# src/config/settings.py (comprehensive update)
from pydantic import BaseSettings, Field, validator
from typing import Optional, Dict, List, Literal
from enum import Enum
import json

class FeatureFlags(BaseSettings):
    """Feature flags for new capabilities"""
    
    # Search and Retrieval
    search_backend: Literal["pgvector", "hybrid"] = Field(
        default="pgvector",
        description="Search backend: pgvector (stable) or hybrid (pgvector + ES)"
    )
    
    enable_hybrid_search: bool = Field(
        default=False,
        description="Enable hybrid keyword + semantic search"
    )
    
    enable_elasticsearch: bool = Field(
        default=False,
        description="Enable Elasticsearch service and indexing"
    )
    
    # Enhancement Features  
    enable_source_highlighting: bool = Field(
        default=False,
        description="Enable source highlighting with page/span info"
    )
    
    enable_pdf_viewer: bool = Field(
        default=False,
        description="Enable PDF viewer with highlights (dev only)"
    )
    
    enable_table_extraction: bool = Field(
        default=False,
        description="Enable structured table extraction and search"
    )
    
    enable_semantic_cache: bool = Field(
        default=False,
        description="Enable semantic similarity-based response caching"
    )
    
    # UI and Demo
    enable_streamlit_demo: bool = Field(
        default=False,
        description="Enable Streamlit demo UI (dev/staging only)"
    )
    
    # Safety and Compliance
    enable_phi_scrubbing: bool = Field(
        default=True,
        description="Enable PHI scrubbing in logs and cache (always enabled in prod)"
    )
    
    enable_response_validation: bool = Field(
        default=True,
        description="Enable medical response safety validation"
    )
    
class HybridSearchConfig(BaseSettings):
    """Hybrid search specific configuration"""
    
    # Elasticsearch
    elasticsearch_url: str = Field(
        default="http://elasticsearch:9200",
        description="Elasticsearch cluster URL"
    )
    
    elasticsearch_index_prefix: str = Field(
        default="edbot",
        description="Prefix for Elasticsearch indices"
    )
    
    elasticsearch_timeout: int = Field(
        default=30,
        description="ES request timeout in seconds"
    )
    
    # Fusion weights by query type
    fusion_weights: Dict[str, List[float]] = Field(
        default={
            "FORM_RETRIEVAL": [0.8, 0.2],     # [keyword_weight, semantic_weight]
            "PROTOCOL_STEPS": [0.7, 0.3],
            "CONTACT_LOOKUP": [0.9, 0.1],
            "CRITERIA_CHECK": [0.4, 0.6],
            "DOSAGE_LOOKUP": [0.6, 0.4],
            "SUMMARY_REQUEST": [0.3, 0.7]
        },
        description="Fusion weights [keyword, semantic] by query type"
    )
    
    # Similarity thresholds
    similarity_thresholds: Dict[str, float] = Field(
        default={
            "FORM_RETRIEVAL": 0.95,
            "PROTOCOL_STEPS": 0.93,
            "CONTACT_LOOKUP": 0.98,
            "CRITERIA_CHECK": 0.90,
            "DOSAGE_LOOKUP": 0.92,
            "SUMMARY_REQUEST": 0.85
        },
        description="Minimum similarity for hybrid result fusion"
    )

class CacheConfig(BaseSettings):
    """Semantic cache configuration"""
    
    # TTL by query type (seconds)
    ttl_by_type: Dict[str, int] = Field(
        default={
            "PROTOCOL_STEPS": 3600,    # 1 hour
            "CRITERIA_CHECK": 1800,    # 30 minutes
            "DOSAGE_LOOKUP": 3600,     # 1 hour
            "SUMMARY_REQUEST": 300,    # 5 minutes
        },
        description="Cache TTL in seconds by query type"
    )
    
    # Types that should never be cached
    never_cache_types: List[str] = Field(
        default=["CONTACT_LOOKUP", "FORM_RETRIEVAL"],
        description="Query types that should never be cached"
    )
    
    # Similarity thresholds for cache hits
    cache_similarity_thresholds: Dict[str, float] = Field(
        default={
            "PROTOCOL_STEPS": 0.95,
            "CRITERIA_CHECK": 0.90,
            "DOSAGE_LOOKUP": 0.93,
            "SUMMARY_REQUEST": 0.85
        },
        description="Minimum similarity for cache hits by query type"
    )
    
    min_confidence_to_cache: float = Field(
        default=0.7,
        description="Minimum response confidence required for caching"
    )

class TableExtractionConfig(BaseSettings):
    """Table extraction configuration"""
    
    extraction_strategy: Literal["unstructured", "camelot", "tabula"] = Field(
        default="unstructured",
        description="Table extraction method"
    )
    
    table_confidence_threshold: float = Field(
        default=0.6,
        description="Minimum confidence for table extraction"
    )
    
    max_table_size: int = Field(
        default=1000,
        description="Maximum number of cells per table"
    )
    
    classify_tables: bool = Field(
        default=True,
        description="Auto-classify table types (dosage, protocol, etc.)"
    )

class HighlightingConfig(BaseSettings):
    """Source highlighting configuration"""
    
    min_highlight_length: int = Field(
        default=20,
        description="Minimum text length for highlights"
    )
    
    context_chars: int = Field(
        default=50,
        description="Characters of context around highlights"
    )
    
    max_highlights_per_response: int = Field(
        default=10,
        description="Maximum number of highlights per response"
    )
    
    bbox_extraction: bool = Field(
        default=True,
        description="Extract bounding boxes for visual highlights"
    )

class Settings(BaseSettings):
    """Main application settings with feature flags"""
    
    # Core settings (existing)
    app_name: str = Field(default="EDBotv8", description="Application name")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Database
    database_url: str = Field(
        default="postgresql://edbot:password@db:5432/edbot_v8",
        description="Database connection URL"
    )
    
    # Redis
    redis_url: str = Field(
        default="redis://redis:6379/0",
        description="Redis connection URL"
    )
    
    # LLM Configuration  
    llm_backend: Literal["gpt-oss", "ollama", "azure"] = Field(
        default="ollama",
        description="LLM backend selection"
    )
    
    # Feature Flags
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    
    # Feature-specific configs
    hybrid_search: HybridSearchConfig = Field(default_factory=HybridSearchConfig)
    cache_config: CacheConfig = Field(default_factory=CacheConfig)
    table_extraction: TableExtractionConfig = Field(default_factory=TableExtractionConfig)
    highlighting: HighlightingConfig = Field(default_factory=HighlightingConfig)
    
    # Environment-specific overrides
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment"
    )
    
    @validator("features")
    def validate_production_features(cls, v, values):
        """Enforce production safety constraints"""
        if values.get("environment") == "production":
            # Force safe defaults in production
            v.enable_pdf_viewer = False
            v.enable_streamlit_demo = False
            v.enable_phi_scrubbing = True
            v.enable_response_validation = True
            
            # Only enable battle-tested features
            if v.enable_hybrid_search or v.enable_table_extraction:
                import warnings
                warnings.warn(
                    "Experimental features enabled in production environment"
                )
        return v
        
    @property
    def is_development(self) -> bool:
        return self.environment == "development"
        
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
        
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"  # Allows FEATURES__ENABLE_HYBRID_SEARCH=true
```

### 2. Environment Configuration Files
```bash
# EDBOTv8.env.example (updated)
# Core Configuration
APP_NAME=EDBotv8
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO

# Database & Cache
DATABASE_URL=postgresql://edbot:password@db:5432/edbot_v8
REDIS_URL=redis://redis:6379/0

# LLM Backend
LLM_BACKEND=ollama
OLLAMA_MODEL=mistral:7b-instruct

# Feature Flags - Search & Retrieval
FEATURES__SEARCH_BACKEND=pgvector
FEATURES__ENABLE_HYBRID_SEARCH=false
FEATURES__ENABLE_ELASTICSEARCH=false

# Feature Flags - Enhancements  
FEATURES__ENABLE_SOURCE_HIGHLIGHTING=false
FEATURES__ENABLE_PDF_VIEWER=false
FEATURES__ENABLE_TABLE_EXTRACTION=false
FEATURES__ENABLE_SEMANTIC_CACHE=false

# Feature Flags - UI & Demo
FEATURES__ENABLE_STREAMLIT_DEMO=false

# Elasticsearch Configuration
HYBRID_SEARCH__ELASTICSEARCH_URL=http://elasticsearch:9200
HYBRID_SEARCH__ELASTICSEARCH_INDEX_PREFIX=edbot
HYBRID_SEARCH__ELASTICSEARCH_TIMEOUT=30

# Cache Configuration
CACHE_CONFIG__MIN_CONFIDENCE_TO_CACHE=0.7

# Table Extraction
TABLE_EXTRACTION__EXTRACTION_STRATEGY=unstructured
TABLE_EXTRACTION__TABLE_CONFIDENCE_THRESHOLD=0.6

# Highlighting
HIGHLIGHTING__MIN_HIGHLIGHT_LENGTH=20
HIGHLIGHTING__CONTEXT_CHARS=50
```

```bash
# .env.development
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Enable dev features
FEATURES__ENABLE_PDF_VIEWER=true
FEATURES__ENABLE_STREAMLIT_DEMO=true
FEATURES__ENABLE_SOURCE_HIGHLIGHTING=true

# More permissive cache settings
CACHE_CONFIG__MIN_CONFIDENCE_TO_CACHE=0.5
```

```bash
# .env.staging  
ENVIRONMENT=staging
FEATURES__ENABLE_HYBRID_SEARCH=true
FEATURES__ENABLE_ELASTICSEARCH=true
FEATURES__ENABLE_SEMANTIC_CACHE=true

# Test new features
FEATURES__ENABLE_TABLE_EXTRACTION=true
FEATURES__ENABLE_SOURCE_HIGHLIGHTING=true
```

```bash
# .env.production
ENVIRONMENT=production
DEBUG=false

# Production-safe features only
FEATURES__SEARCH_BACKEND=pgvector
FEATURES__ENABLE_HYBRID_SEARCH=false
FEATURES__ENABLE_PDF_VIEWER=false
FEATURES__ENABLE_STREAMLIT_DEMO=false

# Strict safety settings
FEATURES__ENABLE_PHI_SCRUBBING=true
FEATURES__ENABLE_RESPONSE_VALIDATION=true
```

### 3. Runtime Configuration Management
```python
# src/config/feature_manager.py
from typing import Dict, Any
import redis
import json
from datetime import datetime, timedelta

class FeatureManager:
    """Runtime feature flag management"""
    
    def __init__(self, redis_client: redis.Redis, settings: Settings):
        self.redis = redis_client
        self.settings = settings
        self.cache_key = "feature_flags"
        self.cache_ttl = 300  # 5 minutes
        
    async def get_flag(self, flag_name: str) -> bool:
        """Get current flag value with caching"""
        
        # Try Redis cache first
        cached = self.redis.get(f"{self.cache_key}:{flag_name}")
        if cached is not None:
            return json.loads(cached)
            
        # Fallback to settings
        flag_value = getattr(self.settings.features, flag_name, False)
        
        # Cache the result
        self.redis.setex(
            f"{self.cache_key}:{flag_name}",
            self.cache_ttl,
            json.dumps(flag_value)
        )
        
        return flag_value
        
    async def set_flag(
        self,
        flag_name: str, 
        value: bool,
        ttl_minutes: int = 60
    ) -> bool:
        """Temporarily override flag value"""
        
        # Validate flag exists
        if not hasattr(self.settings.features, flag_name):
            raise ValueError(f"Unknown feature flag: {flag_name}")
            
        # Don't allow production safety overrides
        if self.settings.is_production:
            safety_flags = [
                "enable_phi_scrubbing",
                "enable_response_validation"
            ]
            if flag_name in safety_flags and not value:
                raise ValueError(f"Cannot disable {flag_name} in production")
                
        # Set temporary override
        self.redis.setex(
            f"{self.cache_key}:{flag_name}",
            ttl_minutes * 60,
            json.dumps(value)
        )
        
        # Log the change
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Feature flag '{flag_name}' temporarily set to {value} "
            f"for {ttl_minutes} minutes"
        )
        
        return True
        
    async def clear_overrides(self):
        """Clear all temporary flag overrides"""
        pattern = f"{self.cache_key}:*"
        keys = self.redis.scan_iter(match=pattern)
        
        deleted = 0
        for key in keys:
            self.redis.delete(key)
            deleted += 1
            
        return deleted
        
    async def get_all_flags(self) -> Dict[str, Any]:
        """Get current state of all feature flags"""
        flags = {}
        
        for field_name, field in self.settings.features.__fields__.items():
            flags[field_name] = {
                "current_value": await self.get_flag(field_name),
                "default_value": field.default,
                "description": field.field_info.description,
                "has_override": self.redis.exists(f"{self.cache_key}:{field_name}")
            }
            
        return flags
```

### 4. Configuration Validation
```python
# src/config/validators.py
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class ConfigurationValidator:
    """Validate configuration consistency"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
    def validate_all(self) -> List[str]:
        """Run all configuration validations"""
        warnings = []
        
        warnings.extend(self._validate_hybrid_search())
        warnings.extend(self._validate_cache_config())
        warnings.extend(self._validate_production_safety())
        warnings.extend(self._validate_dependencies())
        
        for warning in warnings:
            logger.warning(f"Config validation: {warning}")
            
        return warnings
        
    def _validate_hybrid_search(self) -> List[str]:
        """Validate hybrid search configuration"""
        warnings = []
        
        if self.settings.features.enable_hybrid_search:
            if not self.settings.features.enable_elasticsearch:
                warnings.append(
                    "Hybrid search enabled but Elasticsearch disabled"
                )
                
            # Check fusion weights sum to 1.0
            for query_type, weights in self.settings.hybrid_search.fusion_weights.items():
                if abs(sum(weights) - 1.0) > 0.01:
                    warnings.append(
                        f"Fusion weights for {query_type} don't sum to 1.0: {weights}"
                    )
                    
        return warnings
        
    def _validate_cache_config(self) -> List[str]:
        """Validate cache configuration"""
        warnings = []
        
        if self.settings.features.enable_semantic_cache:
            # Check TTL values are reasonable
            for query_type, ttl in self.settings.cache_config.ttl_by_type.items():
                if ttl > 7200:  # 2 hours
                    warnings.append(
                        f"Very long cache TTL for {query_type}: {ttl}s"
                    )
                    
            # Validate never-cache types
            never_cache = self.settings.cache_config.never_cache_types
            if "CONTACT_LOOKUP" not in never_cache:
                warnings.append("CONTACT_LOOKUP should never be cached")
                
        return warnings
        
    def _validate_production_safety(self) -> List[str]:
        """Validate production safety settings"""
        warnings = []
        
        if self.settings.is_production:
            # Ensure safety features enabled
            if not self.settings.features.enable_phi_scrubbing:
                warnings.append("PHI scrubbing disabled in production")
                
            if not self.settings.features.enable_response_validation:
                warnings.append("Response validation disabled in production")
                
            # Warn about experimental features
            experimental = [
                "enable_hybrid_search",
                "enable_table_extraction"
            ]
            for feature in experimental:
                if getattr(self.settings.features, feature):
                    warnings.append(f"Experimental feature {feature} enabled in production")
                    
        return warnings
        
    def _validate_dependencies(self) -> List[str]:
        """Check feature dependencies"""
        warnings = []
        
        # Highlighting requires PDF viewer or highlights are unused
        if (self.settings.features.enable_source_highlighting and 
            not self.settings.features.enable_pdf_viewer):
            warnings.append(
                "Source highlighting enabled without PDF viewer - highlights won't be visible"
            )
            
        # Table extraction without hybrid search reduces effectiveness
        if (self.settings.features.enable_table_extraction and 
            not self.settings.features.enable_hybrid_search):
            warnings.append(
                "Table extraction more effective with hybrid search enabled"
            )
            
        return warnings
```

### 5. Management Endpoints
```python
# src/api/endpoints/admin.py
@router.get("/config/flags")
async def get_feature_flags(
    feature_manager: FeatureManager = Depends(get_feature_manager)
):
    """Get current feature flag status"""
    return await feature_manager.get_all_flags()
    
@router.post("/config/flags/{flag_name}")
async def set_feature_flag(
    flag_name: str,
    enabled: bool,
    ttl_minutes: int = 60,
    feature_manager: FeatureManager = Depends(get_feature_manager)
):
    """Temporarily override feature flag"""
    await feature_manager.set_flag(flag_name, enabled, ttl_minutes)
    return {"status": "updated", "flag": flag_name, "value": enabled}
    
@router.delete("/config/flags")
async def clear_flag_overrides(
    feature_manager: FeatureManager = Depends(get_feature_manager)
):
    """Clear all temporary flag overrides"""
    cleared = await feature_manager.clear_overrides()
    return {"status": "cleared", "count": cleared}
```

## Testing Strategy
```python
# tests/unit/test_configuration.py
def test_production_safety_validation():
    """Test production safety constraints"""
    settings = Settings(environment="production")
    validator = ConfigurationValidator(settings)
    
    # Should enforce safety settings
    assert settings.features.enable_phi_scrubbing is True
    assert settings.features.enable_pdf_viewer is False
    
def test_feature_flag_overrides():
    """Test runtime flag management"""
    feature_manager = FeatureManager(redis_mock, settings)
    
    # Test temporary override
    await feature_manager.set_flag("enable_hybrid_search", True, 1)
    assert await feature_manager.get_flag("enable_hybrid_search") is True
    
    # Should expire
    time.sleep(70)
    assert await feature_manager.get_flag("enable_hybrid_search") is False
```

## Documentation
```markdown
# docs/configuration.md
## Feature Flags Reference

### Search & Retrieval
- `FEATURES__ENABLE_HYBRID_SEARCH`: Enable keyword + semantic fusion
- `FEATURES__ENABLE_ELASTICSEARCH`: Enable Elasticsearch service  

### Enhancement Features
- `FEATURES__ENABLE_SOURCE_HIGHLIGHTING`: Page/span source highlighting
- `FEATURES__ENABLE_TABLE_EXTRACTION`: Structured table extraction
- `FEATURES__ENABLE_SEMANTIC_CACHE`: Similarity-based response caching

### Safety & Compliance  
- `FEATURES__ENABLE_PHI_SCRUBBING`: PHI removal from logs/cache
- `FEATURES__ENABLE_RESPONSE_VALIDATION`: Medical response validation

## Environment-Specific Configs
- Use `.env.development` for local development
- Use `.env.staging` for testing new features
- Use `.env.production` for production deployment
```

## Migration Strategy
1. Add new settings with backward-compatible defaults
2. Update existing code to check feature flags
3. Provide environment-specific example configs
4. Document migration path in README