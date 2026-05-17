"""Polars-интеграция."""
import polars as pl
from datetime import datetime

from pydajet_metadata._types import sa_to_python
from pydajet_metadata.repository import Repository


class PolarsBridge:
    def __init__(self, repo: Repository):
        self._repo = repo

    def read(self, type_name: str, object_name: str) -> pl.DataFrame:
        query = self._repo.query(type_name, object_name)
        rows = query.all()

        if not rows:
            schema = {h: self._polars_type(query, h) for h in query._column_map}
            return pl.DataFrame(schema=schema)

        for child_name in query._children:
            child_query = query._children[child_name]
            child_rows = child_query.all()
            by_owner = {}
            for row in child_rows:
                owner = row.get(child_query._owner_key)
                if owner:
                    by_owner.setdefault(owner, []).append(row)
            for row in rows:
                pk = row.get('Ссылка')
                if pk:
                    row[child_name] = by_owner.get(pk, [])

        return pl.DataFrame(rows)

    def write(self, df: pl.DataFrame, type_name: str, object_name: str, mode: str = 'replace') -> int:
        query = self._repo.query(type_name, object_name)
        if mode == 'replace':
            for row in query.all():
                pk = row.get('Ссылка')
                if pk:
                    query.delete(pk)

        count = 0
        for row in df.to_dicts():
            parts = {}
            for child_name in query._children:
                if child_name in row and row[child_name]:
                    parts[child_name] = row[child_name]
                row.pop(child_name, None)
            query.insert(row)
            pk = row.get('Ссылка')
            if pk and parts:
                for child_name, rows_list in parts.items():
                    child_query = query._children[child_name]
                    for child_row in rows_list:
                        child_row[child_query._owner_key] = pk
                        child_query.insert(child_row)
            count += 1
        return count

    def _polars_type(self, query, col_name: str) -> pl.DataType:
        col = query._table.c[query._column_map[col_name].lower()]
        py_type = sa_to_python(col.type)
        if py_type is str: return pl.Utf8
        if py_type is datetime: return pl.Datetime
        if py_type is bool: return pl.Boolean
        if py_type is int: return pl.Int64
        if py_type is float: return pl.Float64
        return pl.Utf8
