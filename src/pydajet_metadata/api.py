"""FastAPI-генератор."""
from typing import Optional

import uvicorn
from fastapi import FastAPI , HTTPException
from pydantic import Field , create_model

from pydajet_metadata._types import sa_to_python
from pydajet_metadata.repository import Repository


class APIGenerator:
    def __init__(self, repo: Repository, title: str = "1С REST API"):
        self._repo = repo
        self._app = FastAPI(title=title, version="1.0.0")
        self._models = {}

    @property
    def app(self) -> FastAPI:
        return self._app

    def generate(self):
        self._generate_models()
        self._generate_endpoints()
        self._generate_info()
        return self._app

    def _generate_models(self):
        for type_name in self._repo.types():
            for obj_name in self._repo.objects(type_name):
                query = self._repo.query(type_name, obj_name)
                fields = {}
                for human, db_name in query._column_map.items():
                    col = query._table.c[db_name.lower()]
                    py_type = sa_to_python(col.type)
                    fields[human] = (Optional[py_type], Field(default=None))
                response = create_model(f"{obj_name}Response", **fields, __module__=__name__)

                create_fields = {}
                for human, db_name in query._column_map.items():
                    if db_name.lower() in (query._pk, '_version', '_marked'):
                        continue
                    col = query._table.c[db_name.lower()]
                    py_type = sa_to_python(col.type)
                    if col.nullable:
                        create_fields[human] = (Optional[py_type], Field(default=None))
                    else:
                        create_fields[human] = (py_type, Field(...))
                create = create_model(f"{obj_name}Create", **create_fields, __module__=__name__)

                update_fields = {}
                for human, db_name in query._column_map.items():
                    if db_name.lower() == query._pk:
                        continue
                    col = query._table.c[db_name.lower()]
                    py_type = sa_to_python(col.type)
                    update_fields[human] = (Optional[py_type], Field(default=None))
                update = create_model(f"{obj_name}Update", **update_fields, __module__=__name__)

                self._models[f"{type_name}/{obj_name}"] = {
                    'query': query, 'response': response, 'create': create, 'update': update,
                }

    def _generate_endpoints(self):
        for key, m in self._models.items():
            type_name, obj_name = key.split('/')
            prefix = f"/{type_name}/{obj_name}"

            @self._app.get(f"{prefix}", response_model=list[m['response']], tags=[type_name])
            def get_all(skip: int = 0, limit: int = 100):
                rows = m['query'].all()
                return [m['response'](**r) for r in rows[skip:skip + limit]]

            @self._app.get(f"{prefix}/{{id}}", response_model=m['response'], tags=[type_name])
            def get_by_id(id: str):
                row = m['query'].where(m['query']._table.c[m['query']._pk] == id).first()
                if not row:
                    raise HTTPException(404, "Not found")
                return m['response'](**row)

            @self._app.post(f"{prefix}", response_model=m['response'], tags=[type_name])
            def create(data: m['create']):
                new_id = m['query'].insert(data.model_dump(exclude_none=True))
                return m['response'](**m['query'].where(
                    m['query']._table.c[m['query']._pk] == new_id
                ).first())

            @self._app.put(f"{prefix}/{{id}}", response_model=m['response'], tags=[type_name])
            def update(id: str, data: m['update']):
                if not m['query'].update(id, data.model_dump(exclude_none=True)):
                    raise HTTPException(404, "Not found")
                return m['response'](**m['query'].where(
                    m['query']._table.c[m['query']._pk] == id
                ).first())

            @self._app.delete(f"{prefix}/{{id}}", tags=[type_name])
            def delete(id: str):
                if not m['query'].delete(id):
                    raise HTTPException(404, "Not found")
                return {"status": "deleted"}

    def _generate_info(self):
        @self._app.get("/types", tags=["Info"])
        def types():
            return self._repo.types()

        @self._app.get("/types/{type_name}/objects", tags=["Info"])
        def objects(type_name: str):
            return self._repo.objects(type_name)

    def run(self, host="0.0.0.0", port=8000):
        uvicorn.run(self._app, host=host, port=port)
