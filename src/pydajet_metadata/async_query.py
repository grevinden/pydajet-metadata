from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from pydajet_metadata.protocols import IAsyncQuery
from pydajet_metadata.query import Query


class AsyncQuery(IAsyncQuery):
    """Асинхронная оболочка для синхронного Query."""

    def __init__(self, query: Query):
        self._query = query

    @property
    def _table(self) -> Any:
        return self._query._table

    @property
    def _pk(self) -> str:
        return self._query._pk

    @property
    def _owner_key(self) -> str:
        return self._query._owner_key

    @property
    def _children(self) -> Dict[str, "AsyncQuery"]:
        return self._query._children

    @property
    def _column_map(self) -> Any:
        return self._query._column_map

    async def all(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self._query.all)

    async def first(self) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._query.first)

    async def count(self) -> int:
        return await asyncio.to_thread(self._query.count)

    def where(self, *conditions: Any) -> "AsyncQuery":
        self._query.where(*conditions)
        return self

    async def insert(self, data: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> str:
        return await asyncio.to_thread(self._query.insert, data, extra)

    async def update(self, record_id: str, data: Dict[str, Any]) -> bool:
        return await asyncio.to_thread(self._query.update, record_id, data)

    async def delete(self, record_id: str) -> bool:
        return await asyncio.to_thread(self._query.delete, record_id)

    async def lock(
        self,
        mode: str = "exclusive",
        row_id: Optional[str] = None,
        nowait: bool = False,
    ) -> None:
        await asyncio.to_thread(self._query.lock, mode, row_id, nowait)

    async def Изменить(
        self,
        record_id: str,
        data: Dict[str, Any],
        expected_version: Optional[int] = None,
    ) -> bool:
        return await asyncio.to_thread(self._query.Изменить, record_id, data, expected_version)

    async def БезопасноеИзменить(self, record_id: str, data: Dict[str, Any]) -> bool:
        return await asyncio.to_thread(self._query.БезопасноеИзменить, record_id, data)

    async def ПолучитьВерсию(self, record_id: str) -> int:
        return await asyncio.to_thread(self._query.ПолучитьВерсию, record_id)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._query, name)
