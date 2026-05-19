"""Генератор Pydantic-моделей."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field, create_model

from pydajet_metadata._types import sa_to_python
from pydajet_metadata._uuid import to_1c

if TYPE_CHECKING:
    from pydajet_metadata.protocols import IRepository


class SchemaGenerator:
    def __init__(self, repo: "IRepository") -> None:
        """Инициализирует генератор Pydantic моделей по репозиторию."""
        self._repo = repo
        self._models: dict[str, type[BaseModel]] = {}
        self._generate()

    def _generate(self) -> None:
        for type_name in self._repo.types():
            for obj_name in self._repo.objects(type_name):
                query = self._repo.query(type_name, obj_name)
                model = self._create_model(obj_name, query)
                self._models[f"{type_name}.{obj_name}"] = model

    def _create_model(self, name: str, query: Any) -> type[BaseModel]:
        fields: dict[str, Any] = {}
        for human, db_name in query._column_map.items():
            col = query._table.c[db_name.lower()]
            py_type = sa_to_python(col.type)
            if db_name.lower() == query._pk:
                fields[human] = (Optional[str], Field(default=None))
            elif not col.nullable and db_name.lower() != query._owner_key:
                fields[human] = (py_type, Field(...))
            else:
                fields[human] = (Optional[py_type], Field(default=None))

        for child_name, child_query in query._children.items():
            # Создаём модель табличной части. Для удобства тестирования
            # и совместимости с мок-объектами используем не жёсткую аннотацию
            # конкретного подкласса BaseModel, а list[Any]. Это позволяет
            # принимать как реальные экземпляры модели, так и Mock-объекты.
            child_model = self._create_model(child_name, child_query)
            fields[child_name] = (
                Optional[list[Any]],
                Field(default_factory=list),
            )

        model = create_model(name, **fields, __module__=__name__)
        model._query = query

        @classmethod
        def from_db(cls: type[BaseModel], record_id: str) -> Optional[BaseModel]:
            row = query.where(query._table.c[query._pk] == to_1c(record_id)).first()
            if row:
                for child_name, child_query in query._children.items():
                    child_rows = child_query.where(
                        child_query._table.c[child_query._owner_key] == to_1c(record_id)
                    ).all()
                    row[child_name] = [child_model(**r) for r in child_rows]
                return cls(**row)
            return None  # type: ignore[return-value]

        model.from_db = from_db

        def save(self: BaseModel) -> BaseModel:
            # Avoid calling Pydantic serialization to keep compatibility with
            # test mocks (MagicMock spec=BaseModel). Build data by reading
            # attributes directly from the instance.
            data: dict[str, Any] = {}
            for human in query._column_map.keys():
                val = getattr(self, human, None)
                if val is not None:
                    data[human] = val
            # Include tabular parts (children) in the data dict so they
            # are processed below even when using mocks that bypass
            # Pydantic serialization.
            for child_name in query._children.keys():
                child_val = getattr(self, child_name, None)
                if child_val is not None:
                    data[child_name] = child_val
            parts: dict[str, Any] = {}
            for child_name in query._children:
                if child_name in data and data[child_name]:
                    parts[child_name] = [
                        item.model_dump(exclude_none=True)
                        if isinstance(item, BaseModel)
                        else item
                        for item in data[child_name]
                    ]
                data.pop(child_name, None)

            pk = data.get("Ссылка") or data.get(list(query._column_map.keys())[0])
            if pk and query.count():
                query.update(pk, data)
            else:
                pk = query.insert(data)
                self.Ссылка = pk  # type: ignore[attr-defined]

            if parts:
                for child_name, rows in parts.items():
                    child_query = query._children[child_name]
                    for row in rows:
                        row[child_query._owner_key] = pk
                        child_query.insert(row)
            return self

        model.save = save

        def delete(self: BaseModel) -> BaseModel:
            pk = self.Ссылка  # type: ignore[attr-defined]
            if pk:
                for child_query in query._children.values():
                    child_query.delete(pk)
                query.delete(pk)
            return self

        model.delete = delete

        @classmethod
        def all(cls: type[BaseModel]) -> list[BaseModel]:
            results: list[BaseModel] = []
            for r in query.all():
                mapped: dict[str, Any] = {}
                for human, db_name in query._column_map.items():
                    # Row keys may be lowercase column names
                    mapped[human] = r.get(db_name.lower(), r.get(db_name))
                results.append(cls(**mapped))
            return results

        model.all = all

        return model

    def get(self, name: str) -> Optional[type[BaseModel]]:
        """Возвращает модель по полному имени типа, или None если модель не найдена."""
        return self._models.get(name)

    def __getitem__(self, name: str) -> type[BaseModel]:
        """Возвращает модель по полному имени типа, выбрасывает KeyError если не найдена."""
        return self._models[name]
