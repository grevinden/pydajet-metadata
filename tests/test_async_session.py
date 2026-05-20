import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pydajet_metadata.async_session import AsyncSession


@pytest.mark.asyncio
async def test_async_session_reflect_table_calls_sync_reflect_table():
    session_mock = MagicMock()
    session_mock.reflect_table.return_value = "table"

    with patch("pydajet_metadata.async_session.Session", return_value=session_mock):
        async_session = AsyncSession("Host=localhost;Database=TestDB;Username=test;Password=test;", data_source="postgresql")
        with patch("pydajet_metadata.async_session.asyncio.to_thread", new=AsyncMock(return_value="table")) as mock_to_thread:
            result = await async_session.reflect_table("_Reference123")

    assert result == "table"
    mock_to_thread.assert_awaited_once_with(session_mock.reflect_table, "_Reference123")


@pytest.mark.asyncio
async def test_async_session_close_calls_sync_close():
    session_mock = MagicMock()
    session_mock.close = MagicMock()

    with patch("pydajet_metadata.async_session.Session", return_value=session_mock):
        async_session = AsyncSession("Host=localhost;Database=TestDB;Username=test;Password=test;", data_source="postgresql")
        with patch("pydajet_metadata.async_session.asyncio.to_thread", new=AsyncMock(return_value=None)) as mock_to_thread:
            await async_session.close()

    mock_to_thread.assert_awaited_once_with(session_mock.close)


@pytest.mark.asyncio
async def test_async_session_transaction_uses_sync_context_manager():
    session_mock = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = session_mock
    ctx.__exit__.return_value = None
    session_mock.transaction.return_value = ctx

    with patch("pydajet_metadata.async_session.Session", return_value=session_mock):
        async_session = AsyncSession("Host=localhost;Database=TestDB;Username=test;Password=test;", data_source="postgresql")
        with patch("pydajet_metadata.async_session.asyncio.to_thread", new=AsyncMock(side_effect=[None, None, None])) as mock_to_thread:
            async with async_session.transaction() as tx:
                assert tx is async_session

    mock_to_thread.assert_any_await(ctx.__enter__)
    mock_to_thread.assert_any_await(ctx.__exit__, None, None, None)


@pytest.mark.asyncio
async def test_async_session_savepoint_uses_sync_context_manager():
    session_mock = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = session_mock
    ctx.__exit__.return_value = None
    session_mock.savepoint.return_value = ctx

    with patch("pydajet_metadata.async_session.Session", return_value=session_mock):
        async_session = AsyncSession("Host=localhost;Database=TestDB;Username=test;Password=test;", data_source="postgresql")
        with patch("pydajet_metadata.async_session.asyncio.to_thread", new=AsyncMock(side_effect=[None, None, None])) as mock_to_thread:
            async with async_session.savepoint() as sp:
                assert sp is async_session

    mock_to_thread.assert_any_await(ctx.__enter__)
    mock_to_thread.assert_any_await(ctx.__exit__, None, None, None)
