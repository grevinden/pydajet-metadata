from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import cast

from pydajet_metadata.async_query import AsyncQuery
from pydajet_metadata.async_session import AsyncSession
from pydajet_metadata.protocols import IAsyncRepository, IMetadataClient, ITypeAccessor
from pydajet_metadata.repository import Repository
from pydajet_metadata.session import Session


class AsyncRepository(IAsyncRepository):
    """Асинхронная оболочка для синхронного Repository."""

    def __init__(
        self,
        connection_string: str | None = None,
        data_source: str = "postgresql",
        *,
        client: IMetadataClient | None = None,
        session: Session | AsyncSession | None = None,
        client_factory: Callable[[str, str], IMetadataClient] | None = None,
    ) -> None:
        sync_session: Session | None
        if isinstance(session, AsyncSession):
            sync_session = session._inner
        else:
            sync_session = session

        if connection_string is None and sync_session is None:
            raise ValueError("connection_string or session must be provided")

        self._repo = Repository(
            connection_string=connection_string,
            data_source=data_source,
            client=client,
            session=sync_session,
            client_factory=client_factory,
        )
        self._session = AsyncSession.from_session(cast(Session, self._repo.session))

    @property
    def session(self) -> AsyncSession:
        return self._session

    @property
    def root_guid(self) -> str:
        return self._repo.root_guid

    @property
    def metadata_version(self) -> int:
        return self._repo.metadata_version

    async def types(self) -> list[str]:
        return await asyncio.to_thread(self._repo.types)

    async def objects(self, type_name: str) -> list[str]:
        return await asyncio.to_thread(self._repo.objects, type_name)

    async def query(self, type_name: str, object_name: str) -> AsyncQuery:
        query = await asyncio.to_thread(self._repo.query, type_name, object_name)
        return AsyncQuery(query)

    async def check_metadata_actual(self) -> None:
        await asyncio.to_thread(self._repo.check_metadata_actual)

    async def refresh_metadata(self) -> None:
        await asyncio.to_thread(self._repo.refresh_metadata)

    async def close(self) -> None:
        await asyncio.to_thread(self._repo.close)

    def __getattr__(self, name: str) -> ITypeAccessor:
        return cast(ITypeAccessor, getattr(self._repo, name))
