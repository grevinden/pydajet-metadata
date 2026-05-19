"""FastAPI-генератор."""

from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field, create_model
from pydantic.main import BaseModel

from pydajet_metadata._types import sa_to_python
from pydajet_metadata.protocols import IMetadataClient

if TYPE_CHECKING:
    from pydajet_metadata.protocols import IRepository


class APIGenerator:
    """Генератор FastAPI-приложения по репозиторию 1С."""

    def __init__(self, repo: "IRepository", title: str = "1С REST API"):
        """Инициализирует генератор API, принимая репозиторий с метаданными."""
        from fastapi import FastAPI

        self._repo = repo
        self._app = FastAPI(title=title, version="1.0.0")
        self._models: dict[str, dict[str, type[BaseModel]]] = {}

    @property
    def app(self) -> FastAPI:
        """Возвращает сгенерированное FastAPI-приложение."""
        return self._app

    def generate(self) -> FastAPI:
        """Собирает модель, маршруты и информацию, возвращает FastAPI-приложение."""
        self._generate_models()
        self._generate_endpoints()
        self._generate_info()
        return self._app

    def _generate_models(self) -> None:
        for type_name in self._repo.types():
            for obj_name in self._repo.objects(type_name):
                query = self._repo.query(type_name, obj_name)
                fields: dict[str, Any] = {}
                for human, db_name in query._column_map.items():
                    col = query._table.c[db_name.lower()]
                    py_type = sa_to_python(col.type)
                    fields[human] = (Optional[py_type], Field(default=None))
                response = create_model(
                    f"{obj_name}Response", **fields, __module__=__name__
                )

                create_fields: dict[str, Any] = {}
                for human, db_name in query._column_map.items():
                    if db_name.lower() in (query._pk, "_version", "_marked"):
                        continue
                    col = query._table.c[db_name.lower()]
                    py_type = sa_to_python(col.type)
                    if col.nullable:
                        create_fields[human] = (Optional[py_type], Field(default=None))
                    else:
                        create_fields[human] = (py_type, Field(...))
                create = create_model(
                    f"{obj_name}Create", **create_fields, __module__=__name__
                )

                update_fields: dict[str, Any] = {}
                for human, db_name in query._column_map.items():
                    if db_name.lower() == query._pk:
                        continue
                    col = query._table.c[db_name.lower()]
                    py_type = sa_to_python(col.type)
                    update_fields[human] = (Optional[py_type], Field(default=None))
                update = create_model(
                    f"{obj_name}Update", **update_fields, __module__=__name__
                )

                self._models[f"{type_name}/{obj_name}"] = {
                    "query": query,
                    "response": response,
                    "create": create,
                    "update": update,
                }

    def _generate_endpoints(self) -> None:
        for key, models in self._models.items():
            type_name, obj_name = key.split("/")
            prefix = f"/{type_name}/{obj_name}"

            from fastapi import HTTPException

            @self._app.get(
                f"{prefix}",
                response_model=list[models["response"]],
                tags=[type_name],
            )
            def get_all(skip: int = 0, limit: int = 100):
                rows = models["query"].all()
                return [models["response"](**r) for r in rows[skip : skip + limit]]

            @self._app.get(
                f"{prefix}/{{id}}",
                response_model=models["response"],
                tags=[type_name],
            )
            def get_by_id(id: str):
                row = (
                    models["query"].where(models["query"]._table.c[models["query"]._pk] == id).first()
                )
                if not row:
                    raise HTTPException(404, "Not found")
                return models["response"](**row)

            @self._app.post(f"{prefix}", response_model=models["response"], tags=[type_name])
            def create(data: models["create"]):
                new_id = models["query"].insert(data.model_dump(exclude_none=True))
                return models["response"](
                    **models["query"]
                    .where(models["query"]._table.c[models["query"]._pk] == new_id)
                    .first()
                )

            @self._app.put(
                f"{prefix}/{{id}}", response_model=models["response"], tags=[type_name]
            )
            def update(id: str, data: models["update"]):
                if not models["query"].update(id, data.model_dump(exclude_none=True)):
                    raise HTTPException(404, "Not found")
                return models["response"](
                    **models["query"]
                    .where(models["query"]._table.c[models["query"]._pk] == id)
                    .first()
                )

            @self._app.delete(f"{prefix}/{{id}}", tags=[type_name])
            def delete(id: str):
                if not models["query"].delete(id):
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
                'uvicorn is required to run the generated FastAPI app. '
                'Install it with `uv add --dev uvicorn` or add it to your environment.'
            ) from exc

        uvicorn.run(self._app, host=host, port=port)
