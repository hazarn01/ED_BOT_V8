import logging
from typing import AsyncGenerator, Generator, Optional

import redis
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..cache.embedding_service import EmbeddingService, create_embedding_service
from ..cache.redis_client import get_redis_client as get_async_redis_client
from ..cache.semantic_cache import SemanticCache
from ..config.enhanced_settings import EnhancedSettings
from ..config.enhanced_settings import get_settings as get_enhanced_settings
from ..config.feature_manager import FeatureManager
from ..config.enhanced_settings import EnhancedSettings, get_settings
from ..models.async_database import get_async_db_session
from ..models.database import get_db_session as _get_db_session
from ..pipeline.emergency_processor import EmergencyQueryProcessor
from ..search.elasticsearch_client import ElasticsearchClient

logger = logging.getLogger(__name__)


def get_db_session() -> Generator[Session, None, None]:
    """Dependency to get database session"""
    with _get_db_session() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            session.rollback()
            raise
        finally:
            session.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database dependency for FastAPI."""
    async with get_async_db_session() as session:
        yield session


def get_redis_client():
    """Dependency to get Redis client"""
    try:
        # Use settings-based configuration for proper Docker networking
        settings = get_settings()
        client = redis.Redis(
            host=settings.redis_host,  # Uses 'redis' in Docker, 'localhost' locally
            port=settings.redis_port,  # Uses 6379 internally
            db=settings.redis_db,
            decode_responses=True
        )
        client.ping()
        logger.info(f"Redis connected: {settings.redis_host}:{settings.redis_port}")
        return client
    except Exception as e:
        logger.error(f"Redis connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service unavailable",
        )


async def get_llm_client():
    """Get LLM client - supports Azure OpenAI as primary backend."""
    settings = get_settings()

    # Check LLM backend configuration
    if settings.llm_backend == "azure":
        logger.info("🔄 Using Azure OpenAI as primary LLM backend")
        from ..ai.azure_fallback_client import AzureOpenAIClient
        
        client = AzureOpenAIClient(
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            deployment=settings.azure_openai_deployment
        )
        
        # Test Azure connection
        try:
            health_ok = await client.health_check()
            if health_ok:
                logger.info("✅ Azure OpenAI client initialized successfully")
                return client
            else:
                logger.error("❌ Azure OpenAI health check failed")
                raise Exception("Azure OpenAI not available")
        except Exception as e:
            logger.error(f"❌ Azure OpenAI initialization failed: {e}")
            raise
    
    elif settings.llm_backend == "ollama":
        logger.info("🔄 Using Ollama as LLM backend")
        from ..ai.ollama_client import OllamaClient
        
        try:
            client = OllamaClient()
            await client.health_check()
            logger.info("✅ Ollama client initialized successfully")
            return client
        except Exception as e:
            logger.error(f"❌ Ollama unavailable: {e}")
            raise
    
    else:  # Default to GPT-OSS for backward compatibility
        logger.info("🔄 Using GPT-OSS as LLM backend")
        from ..ai.gpt_oss_client import GPTOSSClient

        client = GPTOSSClient(
            base_url=settings.gpt_oss_url,
            model=settings.gpt_oss_model
        )

        # Test connection on startup
        try:
            await client.health_check()
            logger.info("✅ GPT-OSS client initialized successfully")
            return client
        except Exception as e:
            if settings.use_azure_fallback and settings.azure_openai_api_key:
                logger.warning(f"⚠️ GPT-OSS unavailable: {e}, falling back to Azure")
                from ..ai.azure_fallback_client import AzureOpenAIClient
                azure_client = AzureOpenAIClient(
                    endpoint=settings.azure_openai_endpoint,
                    api_key=settings.azure_openai_api_key, 
                    deployment=settings.azure_openai_deployment
                )
                return azure_client
            else:
                logger.error(f"❌ GPT-OSS unavailable and no fallback: {e}")
                raise


async def get_query_processor(
    db: Session = Depends(get_db_session),
    redis_client=Depends(get_redis_client),
    semantic_cache=None  # Temporarily disabled - Depends(get_semantic_cache)
) -> EmergencyQueryProcessor:
    """Dependency to get emergency query processor with QA fallback support"""
    try:
        logger.info(
            "✅ Using Enhanced Emergency Query Processor with QA fallback")
        return EmergencyQueryProcessor(db, redis_client)
    except Exception as e:
        logger.error(f"Emergency processor failed: {e}")
        # Even this fallback uses emergency processor
        return EmergencyQueryProcessor(db, redis_client)


def get_elasticsearch_client(settings: EnhancedSettings = Depends(get_settings)) -> Optional[ElasticsearchClient]:
    """Get Elasticsearch client if hybrid search enabled"""
    if settings.search_backend == "hybrid":
        client = ElasticsearchClient(settings)
        return client if client.get_client() else None
    return None


async def get_embedding_service() -> EmbeddingService:
    """Dependency to get embedding service for semantic cache."""
    try:
        # Use the same LLM client for embeddings
        llm_client = await get_llm_client()
        return create_embedding_service(llm_client)
    except Exception as e:
        logger.error(f"Failed to initialize embedding service: {e}")
        # Return service without model (will use hash fallback)
        return create_embedding_service(None)


async def get_semantic_cache(
    settings: EnhancedSettings = Depends(get_settings),
    embedding_service: EmbeddingService = Depends(get_embedding_service)
) -> Optional[SemanticCache]:
    """Dependency to get semantic cache instance."""
    if not settings.enable_semantic_cache:
        return None

    try:
        # Get async Redis client
        redis_client = await get_async_redis_client()

        # Create semantic cache
        cache = SemanticCache(
            redis_client._client,  # Use the underlying aioredis client
            settings,
            embedding_service
        )

        return cache
    except Exception as e:
        logger.error(f"Failed to initialize semantic cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic cache service unavailable",
        )


async def get_feature_manager(
    enhanced_settings: EnhancedSettings = Depends(get_enhanced_settings)
) -> FeatureManager:
    """Dependency to get feature manager"""
    try:
        return FeatureManager(enhanced_settings)
    except Exception as e:
        logger.error(f"Failed to initialize feature manager: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feature management service unavailable",
        )
