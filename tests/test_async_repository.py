import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pydajet_metadata.async_repository import AsyncRepository
from pydajet_metadata.async_query import AsyncQuery


@pytest.mark.asyncio
async def test_async_repository_types_and_objects_delegate():
    repo_mock = MagicMock()
    repo_mock.types.return_value = ["Catalog"]
    repo_mock.objects.return_value = ["Products"]
    from_session_mock = MagicMock()

    with patch("pydajet_metadata.async_repository.Repository", return_value=repo_mock):
        with patch("pydajet_metadata.async_repository.AsyncSession.from_session", return_value=from_session_mock):
            async_repo = AsyncRepository(connection_string="Host=localhost;Database=TestDB;Username=test;Password=test;", data_source="postgresql")
            with patch("pydajet_metadata.async_repository.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn, *args: fn(*args))) as mock_to_thread:
                assert await async_repo.types() == ["Catalog"]
                assert await async_repo.objects("Catalog") == ["Products"]

    mock_to_thread.assert_any_await(repo_mock.types)
    mock_to_thread.assert_any_await(repo_mock.objects, "Catalog")


@pytest.mark.asyncio
async def test_async_repository_query_returns_async_query():
    repo_mock = MagicMock()
    query_mock = MagicMock()
    repo_mock.query.return_value = query_mock

    with patch("pydajet_metadata.async_repository.Repository", return_value=repo_mock):
        with patch("pydajet_metadata.async_repository.AsyncSession.from_session", return_value=MagicMock()):
            async_repo = AsyncRepository(connection_string="Host=localhost;Database=TestDB;Username=test;Password=test;", data_source="postgresql")
            with patch("pydajet_metadata.async_repository.asyncio.to_thread", new=AsyncMock(side_effect=lambda fn, *args: fn(*args))):
                q = await async_repo.query("Catalog", "Products")

    assert isinstance(q, AsyncQuery)
    repo_mock.query.assert_called_once_with("Catalog", "Products")


@pytest.mark.asyncio
async def test_async_repository_close_calls_sync_close():
    repo_mock = MagicMock()
    repo_mock.close.return_value = None

    with patch("pydajet_metadata.async_repository.Repository", return_value=repo_mock):
        with patch("pydajet_metadata.async_repository.AsyncSession.from_session", return_value=MagicMock()):
            async_repo = AsyncRepository(connection_string="Host=localhost;Database=TestDB;Username=test;Password=test;", data_source="postgresql")
            with patch("pydajet_metadata.async_repository.asyncio.to_thread", new=AsyncMock(return_value=None)) as mock_to_thread:
                await async_repo.close()

    mock_to_thread.assert_awaited_once_with(repo_mock.close)
