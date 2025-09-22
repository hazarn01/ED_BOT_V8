from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra environment variables
    )

    # Application
    app_env: str = "development"
    port: int = 8001
    debug: bool = False

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "edbot"
    db_password: str = "edbot"
    db_name: str = "edbot"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Search backend configuration
    search_backend: Literal["pgvector", "hybrid"] = Field(
        default="pgvector",
        description="Search backend: pgvector (default) or hybrid (pgvector + ES)"
    )
    
    # Elasticsearch settings
    elasticsearch_url: str = Field(
        default="http://elasticsearch:9200",
        description="Elasticsearch URL for hybrid search"
    )
    elasticsearch_index_prefix: str = Field(
        default="edbot",
        description="Index prefix for Elasticsearch"
    )
    elasticsearch_timeout: int = Field(
        default=30,
        description="Elasticsearch request timeout in seconds"
    )
    
    # Fusion weight overrides (optional)
    fusion_weights_json: Optional[str] = Field(
        default=None,
        description="JSON string of custom fusion weights per query type"
    )

    # LLM Configuration - GPT-OSS ONLY
    llm_backend: str = "gpt-oss"  # Changed default to gpt-oss
    
    # GPT-OSS Settings (PRIMARY)
    gpt_oss_url: str = "http://gpt-oss:8000/v1"  # Use container name
    vllm_base_url: str = "http://localhost:8000"  # vLLM server URL
    gpt_oss_model: str = "EleutherAI/gpt-neox-20b"  # The REAL GPT-OSS 20B model!
    gpt_oss_max_tokens: int = 1024
    gpt_oss_temperature: float = 0.0  # Deterministic for medical
    
    # Emergency Azure Fallback (disabled by default)
    azure_openai_endpoint: Optional[str] = None
    azure_openai_api_key: Optional[str] = None
    azure_openai_deployment: Optional[str] = None
    use_azure_fallback: bool = False  # New flag to control fallback

    # LangExtract
    langextract_api_key: Optional[str] = None
    langextract_local_model: str = "llama3.1:8b"  # Updated to Llama 3.1:8b

    # Security/Compliance
    disable_external_calls: bool = True
    log_scrub_phi: bool = True
    trusted_hosts: str = "localhost,127.0.0.1"
    allowed_origins: str = "http://localhost:8001,http://localhost:3000"
    secret_key: str = "development-secret-change-in-production"

    # Cache Configuration
    cache_ttl_contact: int = 300  # 5 minutes
    cache_ttl_protocol: int = 600  # 10 minutes
    cache_ttl_criteria: int = 600  # 10 minutes
    cache_ttl_dosage: int = 450  # 7.5 minutes
    cache_ttl_summary: int = 900  # 15 minutes
    cache_ttl_form: int = 0  # Never cache forms

    # Performance
    max_workers: int = 4
    embedding_batch_size: int = 32
    chunk_size: int = 512
    chunk_overlap: int = 50
    max_query_length: int = 1000

    # Paths
    docs_path: str = "/app/docs"
    static_path: str = "/app/static"
    upload_path: str = "/tmp/uploads"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Model inference settings
    llm_temperature: float = 0.0
    llm_top_p: float = 0.1
    llm_max_tokens: int = 1500
    llm_timeout: int = 30  # seconds
    llm_retry_attempts: int = 3
    llm_retry_delay: float = 1.0  # seconds

    # Medical validation
    enable_medical_validation: bool = True
    require_citations: bool = True
    min_confidence_threshold: float = 0.7
    
    # Source highlighting and PDF viewer (PRP 17-18)
    enable_highlights: bool = Field(
        default=False,
        description="Enable source highlighting in responses"
    )
    enable_pdf_viewer: bool = Field(
        default=False,
        description="Enable PDF viewer endpoint (dev only)"
    )
    viewer_cache_ttl_hours: int = Field(
        default=1,
        description="TTL for viewer response cache in hours"
    )
    
    # Table extraction (PRP 19)
    enable_table_extraction: bool = Field(
        default=False,
        description="Enable table extraction from medical documents"
    )
    table_extraction_confidence_threshold: float = Field(
        default=0.7,
        description="Minimum confidence threshold for extracted tables"
    )
    max_tables_per_document: int = Field(
        default=10,
        description="Maximum number of tables to extract per document"
    )
    
    # Semantic cache (PRP 20)
    enable_semantic_cache: bool = Field(
        default=False,
        description="Enable semantic similarity-based caching"
    )
    semantic_cache_similarity_threshold: float = Field(
        default=0.9,
        description="Default similarity threshold for cache hits"
    )
    semantic_cache_min_confidence: float = Field(
        default=0.7,
        description="Minimum confidence threshold for caching responses"
    )
    semantic_cache_max_entries_per_type: int = Field(
        default=1000,
        description="Maximum cache entries per query type"
    )
    
    # Streamlit demo (PRP 21)
    enable_streamlit_demo: bool = Field(
        default=False,
        description="Enable Streamlit demo UI (dev only)"
    )

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL database URL (sync)."""
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def async_database_url(self) -> str:
        """Construct async PostgreSQL database URL."""
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def redis_url(self) -> str:
        """Construct Redis URL."""
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def trusted_hosts_list(self) -> List[str]:
        """Parse trusted hosts into list."""
        return [h.strip() for h in self.trusted_hosts.split(",")]

    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse allowed origins into list."""
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.app_env == "development"

    def get_cache_ttl(self, query_type: str) -> int:
        """Get cache TTL for a specific query type."""
        ttl_map = {
            "contact": self.cache_ttl_contact,
            "form": self.cache_ttl_form,
            "protocol": self.cache_ttl_protocol,
            "criteria": self.cache_ttl_criteria,
            "dosage": self.cache_ttl_dosage,
            "summary": self.cache_ttl_summary,
        }
        return ttl_map.get(query_type, 300)  # Default 5 minutes


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
