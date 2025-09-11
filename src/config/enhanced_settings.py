"""
Enhanced settings structure for EDBotv8 with comprehensive feature flags.

Provides granular control over features with environment-specific configurations,
safe defaults, and production safety constraints.
"""

import warnings
from typing import Dict, List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Observability
    enable_metrics: bool = Field(
        default=True,
        description="Enable Prometheus metrics collection"
    )

    enable_medical_metrics: bool = Field(
        default=True,
        description="Enable medical domain-specific metrics"
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
            # [keyword_weight, semantic_weight]
            "FORM_RETRIEVAL": [0.8, 0.2],
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


class ObservabilityConfig(BaseSettings):
    """Observability and monitoring configuration"""

    metrics_port: int = Field(
        default=9090,
        description="Port for Prometheus metrics endpoint"
    )

    health_check_interval: int = Field(
        default=30,
        description="Health check interval in seconds"
    )

    performance_alert_threshold: float = Field(
        default=2.0,
        description="Performance degradation alert threshold (multiplier)"
    )

    log_query_metrics: bool = Field(
        default=True,
        description="Log detailed query performance metrics"
    )


class EnhancedSettings(BaseSettings):
    """Main application settings with comprehensive feature flags"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # Allows FEATURES__ENABLE_HYBRID_SEARCH=true
        case_sensitive=False,
        extra="ignore"  # Ignore extra environment variables
    )

    # Core settings
    app_name: str = Field(default="EDBotv8", description="Application name")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="standard", description="Log format type")
    log_scrub_phi: bool = Field(
        default=True, description="Enable PHI scrubbing in logs")
    port: int = Field(default=8001, description="Application port")

    # Database
    db_host: str = Field(default="localhost", description="Database host")
    db_port: int = Field(default=5432, description="Database port")
    db_user: str = Field(default="edbot", description="Database user")
    db_password: str = Field(default="edbot", description="Database password")
    db_name: str = Field(default="edbot_v8", description="Database name")

    # Redis
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")

    # LLM Configuration
    llm_backend: Literal["gpt-oss", "ollama", "azure"] = Field(
        default="ollama",
        description="LLM backend selection"
    )

    ollama_base_url: str = Field(
        default="http://ollama:11434",
        description="Ollama service URL"
    )

    vllm_base_url: str = Field(
        default="http://llm:8000",
        description="vLLM service URL"
    )

    # GPT-OSS settings for compatibility
    gpt_oss_url: str = Field(
        default="http://ollama:11434/v1",
        description="GPT-OSS compatible URL"
    )

    gpt_oss_model: str = Field(
        default="llama3.1:8b",
        description="GPT-OSS compatible model name"
    )

    # Azure fallback settings
    use_azure_fallback: bool = Field(
        default=False,
        description="Enable Azure OpenAI fallback"
    )

    azure_openai_api_key: str = Field(
        default="",
        description="Azure OpenAI API key"
    )

    # Additional compatibility settings
    disable_external_calls: bool = Field(
        default=True,
        description="Disable external API calls for privacy"
    )

    # File paths
    docs_path: str = Field(
        default="./docs",
        description="Path to document storage"
    )

    # Feature Flags
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    # Feature-specific configs
    hybrid_search: HybridSearchConfig = Field(
        default_factory=HybridSearchConfig)
    cache_config: CacheConfig = Field(default_factory=CacheConfig)
    table_extraction: TableExtractionConfig = Field(
        default_factory=TableExtractionConfig)
    highlighting: HighlightingConfig = Field(
        default_factory=HighlightingConfig)
    observability: ObservabilityConfig = Field(
        default_factory=ObservabilityConfig)

    # Environment-specific overrides
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment"
    )

    @field_validator("features")
    def validate_production_features(cls, v, info):
        """Enforce production safety constraints"""
        if hasattr(info, 'data') and info.data.get("environment") == "production":
            # Force safe defaults in production
            v.enable_pdf_viewer = False
            v.enable_streamlit_demo = False
            v.enable_phi_scrubbing = True
            v.enable_response_validation = True

            # Warn about experimental features
            if v.enable_hybrid_search or v.enable_table_extraction:
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

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL database URL."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def async_database_url(self) -> str:
        """Construct async PostgreSQL database URL."""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def redis_url(self) -> str:
        """Construct Redis URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


# Factory function for backward compatibility
def get_settings() -> EnhancedSettings:
    """Get application settings instance."""
    return EnhancedSettings()


# Global settings instance (will be replaced during migration)
settings = get_settings()
