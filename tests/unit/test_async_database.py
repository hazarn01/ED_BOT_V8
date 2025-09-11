"""Test async database connection management."""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.async_database import get_database, init_async_database


@pytest.mark.asyncio
async def test_async_database_context_manager():
    """Test async database context manager."""
    with patch('src.models.async_database.AsyncSessionLocal') as mock_session:
        mock_db = AsyncMock(spec=AsyncSession)
        mock_session.return_value.__aenter__.return_value = mock_db
        
        async with get_database() as db:
            assert db is mock_db
            
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

@pytest.mark.asyncio 
async def test_async_database_rollback_on_error():
    """Test database rollback on exception."""
    with patch('src.models.async_database.AsyncSessionLocal') as mock_session:
        mock_db = AsyncMock(spec=AsyncSession)
        mock_session.return_value.__aenter__.return_value = mock_db
        
        with pytest.raises(ValueError):
            async with get_database():
                raise ValueError("Test error")
                
        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()

@pytest.mark.asyncio
async def test_init_async_database():
    """Test async database initialization."""
    with patch('src.models.async_database.create_async_engine') as mock_create_engine, \
         patch('src.models.async_database.async_sessionmaker') as mock_sessionmaker:
        
        mock_engine = AsyncMock()
        mock_create_engine.return_value = mock_engine
        
        init_async_database()
        
        # Verify engine was created with correct parameters
        mock_create_engine.assert_called_once()
        call_args = mock_create_engine.call_args
        assert call_args[1]['pool_size'] == 10
        assert call_args[1]['max_overflow'] == 20
        assert call_args[1]['pool_pre_ping'] is True
        assert call_args[1]['pool_recycle'] == 300
        
        # Verify sessionmaker was configured
        mock_sessionmaker.assert_called_once_with(
            mock_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )