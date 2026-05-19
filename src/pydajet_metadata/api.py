"""FastAPI-генератор."""

from typing import TYPE_CHECKING, Optional

import sys
import types

from pydantic import BaseModel, Field

from pydajet_metadata._pydantic_factory import ModelFieldSpec, dynamic_model, response_list

from pydajet_metadata._api_types import ObjectRouteBundle
from pydajet_metadata._types import sa_to_python
from pydajet_metadata.protocols import IRepository, RowDict

if TYPE_CHECKING:
    from fastapi import FastAPI

# Поддержка monkeypatch.setattr('pydajet_metadata.api.uvicorn.run', ...)
_uvicorn_mod_name = f"{__name__}.uvicorn"
_real_uvicorn: types.ModuleType | None
try:
    import uvicorn as _real_uvicorn  # pragma: no cover - optional dependency
except Exception:
    _real_uvicorn = None

if _real_uvicorn is not None:
    sys.modules[_uvicorn_mod_name] = _real_uvicorn
    uvicorn = _real_uvicorn
else:
    if _uvicorn_mod_name not in sys.modules:
        _fake = types.ModuleType(_uvicorn_mod_name)
        sys.modules[_uvicorn_mod_name] = _fake
    uvicorn = sys.modules[_uvicorn_mod_name]


class APIGenerator:
    """Генератор FastAPI-приложения по репозиторию 1С."""

    def __init__(self, repo: IRepository, title: str = "1С REST API"):
        """Инициализирует генератор API, принимая репозиторий с метаданными."""
        from fastapi import FastAPI

        self._repo = repo
        self._app = FastAPI(title=title, version="1.0.0")
        self._models: dict[str, ObjectRouteBundle] = {}

    @property
    def app(self) -> "FastAPI":
        """Возвращает сгенерированное FastAPI-приложение."""
        return self._app

    def generate(self) -> "FastAPI":
        """Собирает модель, маршруты и информацию, возвращает FastAPI-приложение."""
        self._generate_models()
        self._generate_endpoints()
        self._generate_info()
        return self._app

    def _generate_models(self) -> None:
        for type_name in self._repo.types():
            for obj_name in self._repo.objects(type_name):
                query = self._repo.query(type_name, obj_name)
                fields: dict[str, ModelFieldSpec] = {}
                for human, db_name in query._column_map.items():
                    try:
                        col = query._table.c[db_name.lower()]
                        py_type = sa_to_python(col.type)
                    except (KeyError, AttributeError, TypeError):
                        py_type = str
                    fields[human] = (Optional[py_type], Field(default=None))
                response = dynamic_model(f"{obj_name}Response", fields, module=__name__)

                create_fields: dict[str, ModelFieldSpec] = {}
                for human, db_name in query._column_map.items():
                    if db_name.lower() in (query._pk, "_version", "_marked"):
                        continue
                    col = query._table.c[db_name.lower()]
                    py_type = sa_to_python(col.type)
                    if col.nullable:
                        create_fields[human] = (Optional[py_type], Field(default=None))
                    else:
                        create_fields[human] = (py_type, Field(...))
                create = dynamic_model(f"{obj_name}Create", create_fields, module=__name__)

                update_fields: dict[str, ModelFieldSpec] = {}
                for human, db_name in query._column_map.items():
                    if db_name.lower() == query._pk:
                        continue
                    col = query._table.c[db_name.lower()]
                    py_type = sa_to_python(col.type)
                    update_fields[human] = (Optional[py_type], Field(default=None))
                update = dynamic_model(f"{obj_name}Update", update_fields, module=__name__)

                self._models[f"{type_name}/{obj_name}"] = ObjectRouteBundle(
                    query=query,
                    response=response,
                    create=create,
                    update=update,
                )

    def _generate_endpoints(self) -> None:
        for key, bundle in self._models.items():
            type_name, obj_name = key.split("/")
            self._register_object_routes(type_name, obj_name, bundle)

    def _register_object_routes(
        self, type_name: str, obj_name: str, bundle: ObjectRouteBundle
    ) -> None:
        from fastapi import HTTPException

        query = bundle["query"]
        response_cls = bundle["response"]
        create_cls = bundle["create"]
        update_cls = bundle["update"]
        prefix = f"/{type_name}/{obj_name}"

        @self._app.get(
            f"{prefix}",
            response_model=response_list(response_cls),
            tags=[type_name],
        )
        def get_all(skip: int = 0, limit: int = 100) -> list[BaseModel]:
            rows = query.all()
            return [response_cls.model_validate(r) for r in rows[skip : skip + limit]]

        @self._app.get(
            f"{prefix}/{{id}}",
            response_model=response_cls,
            tags=[type_name],
        )
        def get_by_id(id: str) -> BaseModel:
            row = query.where(query._table.c[query._pk] == id).first()
            if not row:
                raise HTTPException(404, "Not found")
            return response_cls.model_validate(row)

        @self._app.post(f"{prefix}", response_model=response_cls, tags=[type_name])
        def create_row(data: RowDict) -> BaseModel:
            validated = create_cls.model_validate(data)
            new_id = query.insert(validated.model_dump(exclude_none=True))
            inserted = query.where(query._table.c[query._pk] == new_id).first()
            if inserted is None:
                raise HTTPException(500, "Insert failed")
            return response_cls.model_validate(inserted)

        @self._app.put(
            f"{prefix}/{{id}}", response_model=response_cls, tags=[type_name]
        )
        def update_row(id: str, data: RowDict) -> BaseModel:
            validated = update_cls.model_validate(data)
            if not query.update(id, validated.model_dump(exclude_none=True)):
                raise HTTPException(404, "Not found")
            row = query.where(query._table.c[query._pk] == id).first()
            if row is None:
                raise HTTPException(404, "Not found")
            return response_cls.model_validate(row)

        @self._app.delete(f"{prefix}/{{id}}", tags=[type_name])
        def delete_row(id: str) -> dict[str, str]:
            if not query.delete(id):
                raise HTTPException(404, "Not found")
            return {"status": "deleted"}

    def _generate_info(self) -> None:
        @self._app.get("/types", tags=["Info"])
        def types() -> list[str]:
            return self._repo.types()

        @self._app.get(r"/types/{type_name}/objects", tags=["Info"])
        def objects(type_name: str) -> list[str]:
            return self._repo.objects(type_name)

    def run(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """Запускает FastAPI-сервер на указанном хосте и порту."""
        try:
            import uvicorn
        except ImportError as exc:
            raise ImportError(
                "uvicorn is required to run the generated FastAPI app. "
                "Install it with `uv add --dev uvicorn` or add it to your environment."
            ) from exc

        uvicorn.run(self._app, host=host, port=port)
