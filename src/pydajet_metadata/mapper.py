# src/pydajet_metadata/mapper.py
"""ColumnMapper: преобразование human ↔ db ↔ python для одной таблицы."""

from __future__ import annotations

from typing import Protocol

from sqlalchemy import LargeBinary
from sqlalchemy.sql.schema import Column, Table

from pydajet_metadata._uuid import format_uuid, from_1c, to_1c
from pydajet_metadata.protocols import ColumnMap, RowDict


class RowLike(Protocol):
    def __getattr__(self, name: str) -> object: ...


class ColumnMapper:
    """
    Маппинг имён колонок между человеческим форматом и БД.

    Отвечает ТОЛЬКО за преобразование имён и значений.
    Не зависит от Query, Session, транзакций.
    """

    def __repr__(self) -> str:
        return f"ColumnMapper(columns={len(self._column_map)})"

    def __init__(self, table: Table, column_map: ColumnMap) -> None:
        self._table = table
        self._column_map = column_map
        self._reverse_map = {v.lower(): k for k, v in column_map.items()}

    def human_to_db(self, data: RowDict) -> dict[str, object]:
        db_data: dict[str, object] = {}
        for human_name, value in data.items():
            if human_name in self._column_map:
                db_name = self._column_map[human_name].lower()
                if isinstance(value, str) and self._is_binary(db_name):
                    try:
                        value = to_1c(value)
                    except (ValueError, AttributeError):
                        pass
                db_data[db_name] = value
            elif human_name.lower() in self._column_map:
                db_data[human_name] = value
            else:
                db_data[human_name.lower()] = value
        return db_data

    def db_to_human(self, row: RowLike) -> RowDict:
        d: RowDict = {}
        for col in self._table.columns:
            human_name = self._reverse_map.get(col.name.lower(), col.name)
            val = getattr(row, col.name)
            if isinstance(val, bytes) and len(val) == 16:
                val = format_uuid(from_1c(val))
            elif isinstance(val, bytes):
                val = val.hex()
            d[human_name] = val
        return d

    def get_db_column(self, human_name: str) -> Column[object]:
        if human_name in self._column_map:
            db_name = self._column_map[human_name].lower()
            if db_name in self._table.c:
                return self._table.c[db_name]
        raise KeyError(f"Column '{human_name}' not found in mapping")

    @property
    def human_names(self) -> list[str]:
        return list(self._column_map.keys())

    @property
    def db_names(self) -> list[str]:
        return [v.lower() for v in self._column_map.values()]

    def _is_binary(self, db_name: str) -> bool:
        return db_name in self._table.c and isinstance(
            self._table.c[db_name].type, LargeBinary
        )
