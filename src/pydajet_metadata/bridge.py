"""Polars-интеграция."""
from datetime import datetime
from typing import TYPE_CHECKING, cast

import polars as pl

from pydajet_metadata._types import sa_to_python
from pydajet_metadata.protocols import RowDict
from pydajet_metadata.query import Query

if TYPE_CHECKING:
    from pydajet_metadata.protocols import IRepository


class PolarsBridge:
    """Интегратор данных в Polars DataFrame."""

    def __init__(self, repo: "IRepository"):
        """Инициализирует мост для чтения и записи данных из репозитория."""
        self._repo = repo

    def read(self, type_name: str, object_name: str) -> pl.DataFrame:
        """Читает таблицу и возвращает DataFrame, включая табличные части."""
        query = cast(Query, self._repo.query(type_name, object_name))
        rows = query.all()

        if not rows:
            schema: dict[str, pl.DataType] = {
                h: self._polars_type(query, h) for h in query._column_map
            }
            return pl.DataFrame(schema=schema)

        for child_name in query._children:
            child_query = query._children[child_name]
            child_rows = child_query.all()
            by_owner: dict[str, list[RowDict]] = {}
            for row in child_rows:
                owner = row.get(child_query._owner_key)
                if isinstance(owner, str):
                    by_owner.setdefault(owner, []).append(row)
            for row in rows:
                pk = row.get("Ссылка")
                if isinstance(pk, str):
                    row[child_name] = by_owner.get(pk, [])
                else:
                    row[child_name] = []

        return pl.DataFrame(rows)

    def write(self, df: pl.DataFrame, type_name: str, object_name: str, mode: str = 'replace') -> int:
        """Записывает строки из DataFrame в репозиторий.

        Args:
            df: DataFrame для записи.
            type_name: тип метаданных.
            object_name: имя объекта.
            mode: режим записи ('replace' или 'append').

        Returns:
            Количество вставленных записей.
        """
        query = cast(Query, self._repo.query(type_name, object_name))
        if mode == 'replace':
            for row in query.all():
                pk = row.get("Ссылка")
                if isinstance(pk, str):
                    query.delete(pk)

        count = 0
        for row in df.to_dicts():
            parts: dict[str, list[RowDict]] = {}
            for child_name in query._children:
                child_val = row.get(child_name)
                if isinstance(child_val, list):
                    parts[child_name] = child_val
                row.pop(child_name, None)
            inserted_pk = query.insert(row)
            pk = row.get("Ссылка")
            pk_str = pk if isinstance(pk, str) else inserted_pk
            if pk_str and parts:
                for child_name, rows_list in parts.items():
                    child_query = query._children[child_name]
                    for child_row in rows_list:
                        child_row[child_query._owner_key] = pk_str
                        child_query.insert(child_row)
            count += 1
        return count

    def _polars_type(self, query: Query, col_name: str) -> pl.DataType:
        col = query._table.c[query._column_map[col_name].lower()]
        py_type = sa_to_python(col.type)
        if py_type is str:
            return pl.Utf8()
        if py_type is datetime:
            return pl.Datetime()
        if py_type is bool:
            return pl.Boolean()
        if py_type is int:
            return pl.Int64()
        if py_type is float:
            return pl.Float64()
        return pl.Utf8()
