from __future__ import annotations

import asyncio
from typing import Literal

from sqlalchemy.sql.schema import Column, Table

from pydajet_metadata._sql_types import SqlWhereClause
from pydajet_metadata.protocols import ColumnMap, IAsyncQuery, RowDict
from pydajet_metadata.query import Query


class AsyncQuery(IAsyncQuery):
    """Асинхронная оболочка для синхронного Query."""

    def __init__(self, query: Query) -> None:
        self._query = query

    @property
    def _table(self) -> Table:
        return self._query._table

    @property
    def _pk(self) -> str:
        return self._query._pk

    @property
    def _owner_key(self) -> str:
        return self._query._owner_key

    @property
    def _children(self) -> dict[str, IAsyncQuery]:
        return {name: AsyncQuery(child) for name, child in self._query._children.items()}

    @property
    def _column_map(self) -> ColumnMap:
        return self._query._column_map

    async def all(self) -> list[RowDict]:
        return await asyncio.to_thread(self._query.all)

    async def first(self) -> RowDict | None:
        return await asyncio.to_thread(self._query.first)

    async def count(self) -> int:
        return await asyncio.to_thread(self._query.count)

    def where(self, *conditions: SqlWhereClause) -> AsyncQuery:
        self._query.where(*conditions)
        return self

    async def insert(self, data: RowDict, extra: RowDict | None = None) -> str:
        return await asyncio.to_thread(self._query.insert, data, extra)

    async def update(self, record_id: str, data: RowDict) -> bool:
        return await asyncio.to_thread(self._query.update, record_id, data)

    async def delete(self, record_id: str) -> bool:
        return await asyncio.to_thread(self._query.delete, record_id)

    async def lock(
        self,
        mode: Literal["exclusive", "shared"] = "exclusive",
        row_id: str | None = None,
        nowait: bool = False,
    ) -> None:
        await asyncio.to_thread(self._query.lock, mode, row_id, nowait)

    async def Изменить(
        self,
        record_id: str,
        data: RowDict,
        expected_version: int | None = None,
    ) -> bool:
        return await asyncio.to_thread(
            self._query.Изменить, record_id, data, expected_version
        )

    async def БезопасноеИзменить(self, record_id: str, data: RowDict) -> bool:
        return await asyncio.to_thread(self._query.БезопасноеИзменить, record_id, data)

    async def ПолучитьВерсию(self, record_id: str) -> int:
        return await asyncio.to_thread(self._query.ПолучитьВерсию, record_id)

    def __getattr__(self, name: str) -> object:
        return getattr(self._query, name)
