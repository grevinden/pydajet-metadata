import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pydajet_metadata.async_query import AsyncQuery


@pytest.mark.asyncio
async def test_async_query_all_delegates_to_sync_query():
    sync_query = MagicMock()
    sync_query.all.return_value = [{"id": 1}]

    async_query = AsyncQuery(sync_query)
    with patch("pydajet_metadata.async_query.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn, *args: fn(*args))) as mock_to_thread:
        result = await async_query.all()

    assert result == [{"id": 1}]
    mock_to_thread.assert_awaited_once_with(sync_query.all)


@pytest.mark.asyncio
async def test_async_query_where_returns_self_and_delegates():
    sync_query = MagicMock()
    async_query = AsyncQuery(sync_query)
    result = async_query.where(sync_query._table.c.some == 1)
    assert result is async_query
    sync_query.where.assert_called_once()


@pytest.mark.asyncio
async def test_async_query_getattr_delegates_to_sync_query():
    sync_query = MagicMock()
    sync_query.some_attr = 42
    async_query = AsyncQuery(sync_query)
    assert async_query.some_attr == 42
