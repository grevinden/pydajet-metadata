"""Методы, привязываемые к динамическим Pydantic-моделям SchemaGenerator."""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel

from pydajet_metadata.protocols import RowDict
from pydajet_metadata._uuid import to_1c
from pydajet_metadata.query import Query


def schema_from_db(
    query: Query,
    child_models: dict[str, type[BaseModel]],
    model_cls: type[BaseModel],
    record_id: str,
) -> BaseModel | None:
    row = query.where(query._table.c[query._pk] == to_1c(record_id)).first()
    if row is None:
        return None
    for child_name, child_query in query._children.items():
        child_model = child_models[child_name]
        child_rows = child_query.where(
            child_query._table.c[child_query._owner_key] == to_1c(record_id)
        ).all()
        row[child_name] = [child_model(**r) for r in child_rows]
    return model_cls(**row)


def bind_from_db(
    model_cls: type[BaseModel],
    query: Query,
    child_models: dict[str, type[BaseModel]],
) -> None:
    def from_db(cls: type[BaseModel], record_id: str) -> BaseModel | None:
        return schema_from_db(query, child_models, cls, record_id)

    setattr(model_cls, "from_db", classmethod(from_db))


def schema_save(instance: BaseModel, query: Query) -> BaseModel:
    data: RowDict = {}
    for human in query._column_map.keys():
        val = getattr(instance, human, None)
        if val is not None:
            data[human] = val
    for child_name in query._children.keys():
        child_val = getattr(instance, child_name, None)
        if child_val is not None:
            data[child_name] = child_val
    parts: dict[str, list[RowDict]] = {}
    for child_name in query._children:
        if child_name in data and data[child_name]:
            raw = data.pop(child_name)
            if isinstance(raw, list):
                parts[child_name] = [
                    item.model_dump(exclude_none=True)
                    if isinstance(item, BaseModel)
                    else cast(RowDict, item)
                    for item in raw
                ]
    pk = data.get("Ссылка")
    if pk is None and query._column_map:
        pk = data.get(next(iter(query._column_map.keys())))
    if pk and query.count():
        query.update(str(pk), data)
    else:
        pk = query.insert(data)
        setattr(instance, "Ссылка", pk)
    if parts:
        for child_name, rows in parts.items():
            child_query = query._children[child_name]
            for row in rows:
                row[child_query._owner_key] = pk
                child_query.insert(row)
    return instance


def bind_save(model_cls: type[BaseModel], query: Query) -> None:
    def save(self: BaseModel) -> BaseModel:
        return schema_save(self, query)

    setattr(model_cls, "save", save)


def schema_delete(instance: BaseModel, query: Query) -> BaseModel:
    pk = getattr(instance, "Ссылка", None)
    if pk:
        for child_query in query._children.values():
            child_query.delete(str(pk))
        query.delete(str(pk))
    return instance


def bind_delete(model_cls: type[BaseModel], query: Query) -> None:
    def delete(self: BaseModel) -> BaseModel:
        return schema_delete(self, query)

    setattr(model_cls, "delete", delete)


def schema_all(model_cls: type[BaseModel], query: Query) -> list[BaseModel]:
    results: list[BaseModel] = []
    for row in query.all():
        mapped: RowDict = {}
        for human, db_name in query._column_map.items():
            mapped[human] = row.get(db_name.lower(), row.get(db_name))
        results.append(model_cls(**mapped))
    return results


def bind_all(model_cls: type[BaseModel], query: Query) -> None:
    def all_rows(cls: type[BaseModel]) -> list[BaseModel]:
        return schema_all(cls, query)

    setattr(model_cls, "all", classmethod(all_rows))
