"""Генератор Pydantic-моделей."""

from __future__ import annotations

from typing import Optional, cast

from pydantic import BaseModel, Field

from pydajet_metadata._pydantic_factory import ModelFieldSpec, dynamic_model

from pydajet_metadata._schema_methods import (
    bind_all,
    bind_delete,
    bind_from_db,
    bind_save,
)
from pydajet_metadata._types import sa_to_python
from pydajet_metadata._uuid import to_1c  # re-export for tests patching schema.to_1c
from pydajet_metadata.protocols import IRepository, RowDict
from pydajet_metadata.query import Query

class SchemaGenerator:
    def __init__(self, repo: IRepository) -> None:
        """Инициализирует генератор Pydantic моделей по репозиторию."""
        self._repo = repo
        self._models: dict[str, type[BaseModel]] = {}
        self._generate()

    def _generate(self) -> None:
        for type_name in self._repo.types():
            for obj_name in self._repo.objects(type_name):
                query = cast(Query, self._repo.query(type_name, obj_name))
                model = self._create_model(obj_name, query)
                self._models[f"{type_name}.{obj_name}"] = model

    def _create_model(self, name: str, query: Query) -> type[BaseModel]:
        fields: dict[str, ModelFieldSpec] = {}
        for human, db_name in query._column_map.items():
            col = query._table.c[db_name.lower()]
            py_type = sa_to_python(col.type)
            if db_name.lower() == query._pk:
                fields[human] = (Optional[str], Field(default=None))
            elif not col.nullable and db_name.lower() != query._owner_key:
                fields[human] = (py_type, Field(...))
            else:
                fields[human] = (Optional[py_type], Field(default=None))

        child_models: dict[str, type[BaseModel]] = {}
        for child_name, child_query in query._children.items():
            child_models[child_name] = self._create_model(child_name, child_query)
            fields[child_name] = (
                Optional[list[BaseModel]],
                Field(default_factory=list),
            )

        model = dynamic_model(name, fields, module=__name__)
        setattr(model, "_query", query)
        bind_from_db(model, query, child_models)
        bind_save(model, query)
        bind_delete(model, query)
        bind_all(model, query)
        return model

    def get(self, name: str) -> Optional[type[BaseModel]]:
        """Возвращает модель по полному имени типа, или None если модель не найдена."""
        return self._models.get(name)

    def __getitem__(self, name: str) -> type[BaseModel]:
        """Возвращает модель по полному имени типа, выбрасывает KeyError если не найдена."""
        return self._models[name]
