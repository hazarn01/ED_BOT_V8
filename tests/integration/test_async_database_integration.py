"""Integration tests for async database."""
import pytest
from sqlalchemy import text

from src.models.async_database import get_database


@pytest.mark.asyncio
async def test_async_database_connection():
    """Test actual async database connection."""
    async with get_database() as db:
        result = await db.execute(text("SELECT 1 as test"))
        row = result.fetchone()
        assert row[0] == 1

@pytest.mark.asyncio
async def test_async_health_check_query():
    """Test health check query through async database."""
    async with get_database() as db:
        result = await db.execute(text("SELECT version() as pg_version"))
        row = result.fetchone()
        assert "PostgreSQL" in str(row[0])

@pytest.mark.asyncio
async def test_async_database_transaction_rollback():
    """Test transaction rollback in async database."""
    try:
        async with get_database() as db:
            # Execute a valid query first
            await db.execute(text("SELECT 1"))
            # Then force an error
            await db.execute(text("SELECT invalid_column FROM nonexistent_table"))
    except Exception:
        # Exception is expected, transaction should have been rolled back
        pass
    
    # Verify database is still accessible after error
    async with get_database() as db:
        result = await db.execute(text("SELECT 1 as recovery_test"))
        row = result.fetchone()
        assert row[0] == 1

@pytest.mark.asyncio
async def test_async_database_concurrent_connections():
    """Test multiple concurrent async database connections."""
    async def make_query():
        async with get_database() as db:
            result = await db.execute(text("SELECT pg_backend_pid() as pid"))
            return result.fetchone()[0]
    
    # Run multiple queries concurrently
    import asyncio
    pids = await asyncio.gather(*[make_query() for _ in range(3)])
    
    # Each connection should have a different backend PID
    assert len(set(pids)) == 3