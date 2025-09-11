"""
Async database connection management for EDBotv8.
Provides async context managers and session factories following FastAPI best practices.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings

logger = logging.getLogger(__name__)

# Async engine and session factory
async_engine = None
AsyncSessionLocal = None

def init_async_database():
    """Initialize async database engine and session factory."""
    global async_engine, AsyncSessionLocal
    
    # Use the async database URL directly
    async_db_url = settings.async_database_url
    
    async_engine = create_async_engine(
        async_db_url,
        echo=settings.is_development,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=300
    )
    
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    logger.info(f"Async database initialized: {async_db_url}")

@asynccontextmanager
async def get_database() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    Used by health monitoring and other async components.
    
    Usage:
        async with get_database() as db:
            result = await db.execute(text("SELECT 1"))
    """
    if AsyncSessionLocal is None:
        init_async_database()
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async database sessions."""
    async with get_database() as session:
        yield session