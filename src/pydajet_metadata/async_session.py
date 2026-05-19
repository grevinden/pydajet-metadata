from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.engine import Engine
from sqlalchemy.sql.schema import Table
from pydajet_metadata.protocols import IAsyncSession
from pydajet_metadata.session import Session


class AsyncSession(IAsyncSession):
    """Асинхронная оболочка для синхронного Session."""

    def __init__(self, connection_string: str, data_source: str = "postgresql") -> None:
        self._inner = Session(connection_string, data_source)

    @classmethod
    def from_session(cls, session: Session) -> AsyncSession:
        self = cls.__new__(cls)
        self._inner = session
        return self

    @property
    def engine(self) -> Engine:
        return self._inner.engine

    async def reflect_table(self, table_name: str) -> Table:
        return await asyncio.to_thread(self._inner.reflect_table, table_name)

    async def get_pk(self, table_name: str) -> str:
        return await asyncio.to_thread(self._inner.get_pk, table_name)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        ctx = self._inner.transaction()
        await asyncio.to_thread(ctx.__enter__)
        try:
            yield self
        except Exception as exc:
            await asyncio.to_thread(ctx.__exit__, type(exc), exc, exc.__traceback__)
            raise
        else:
            await asyncio.to_thread(ctx.__exit__, None, None, None)

    @asynccontextmanager
    async def savepoint(self) -> AsyncIterator[AsyncSession]:
        ctx = self._inner.savepoint()
        await asyncio.to_thread(ctx.__enter__)
        try:
            yield self
        except Exception as exc:
            await asyncio.to_thread(ctx.__exit__, type(exc), exc, exc.__traceback__)
            raise
        else:
            await asyncio.to_thread(ctx.__exit__, None, None, None)

    async def close(self) -> None:
        await asyncio.to_thread(self._inner.close)
