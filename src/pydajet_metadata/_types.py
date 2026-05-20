"""Маппинг типов PostgreSQL → SQLAlchemy → Python."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy.types import (
    Boolean,
    DateTime,
    Float,
    Integer,
    LargeBinary,
    String,
    TypeEngine,
)

PG_TO_SA: dict[str, type[TypeEngine[object]]] = {
    "bytea": cast(type[TypeEngine[object]], LargeBinary),
    "integer": cast(type[TypeEngine[object]], Integer),
    "boolean": cast(type[TypeEngine[object]], Boolean),
    "timestamp": cast(type[TypeEngine[object]], DateTime),
    "datetime": cast(type[TypeEngine[object]], DateTime),
    "datetime2": cast(type[TypeEngine[object]], DateTime),
    "datetimeoffset": cast(type[TypeEngine[object]], DateTime),
    "smalldatetime": cast(type[TypeEngine[object]], DateTime),
    "date": cast(type[TypeEngine[object]], DateTime),
    "time": cast(type[TypeEngine[object]], DateTime),
    "character varying": cast(type[TypeEngine[object]], String),
    "nvarchar": cast(type[TypeEngine[object]], String),
    "nchar": cast(type[TypeEngine[object]], String),
    "varchar": cast(type[TypeEngine[object]], String),
    "char": cast(type[TypeEngine[object]], String),
    "mvarchar": cast(type[TypeEngine[object]], String),
    "text": cast(type[TypeEngine[object]], String),
    "ntext": cast(type[TypeEngine[object]], String),
    "uniqueidentifier": cast(type[TypeEngine[object]], String),
    "numeric": cast(type[TypeEngine[object]], Float),
    "decimal": cast(type[TypeEngine[object]], Float),
    "money": cast(type[TypeEngine[object]], Float),
    "smallmoney": cast(type[TypeEngine[object]], Float),
    "double precision": cast(type[TypeEngine[object]], Float),
    "real": cast(type[TypeEngine[object]], Float),
    "float": cast(type[TypeEngine[object]], Float),
    "bigint": cast(type[TypeEngine[object]], Integer),
    "smallint": cast(type[TypeEngine[object]], Integer),
    "tinyint": cast(type[TypeEngine[object]], Integer),
    "bit": cast(type[TypeEngine[object]], Boolean),
    "binary": cast(type[TypeEngine[object]], LargeBinary),
    "varbinary": cast(type[TypeEngine[object]], LargeBinary),
    "image": cast(type[TypeEngine[object]], LargeBinary),
}

SA_TO_PYTHON: dict[str, type[object]] = {
    "string": str,
    "varchar": str,
    "mvarchar": str,
    "text": str,
    "datetime": datetime,
    "timestamp": datetime,
    "boolean": bool,
    "integer": int,
    "bigint": int,
    "smallint": int,
    "float": float,
    "numeric": float,
    "decimal": float,
    "double precision": float,
    "real": float,
    "bytea": bytes,
    "binary": bytes,
    "largebinary": bytes,
}


def pg_to_sqlalchemy(pg_type: str) -> type[TypeEngine[object]]:
    pg_type = pg_type.lower()
    for key, sa_type in PG_TO_SA.items():
        if key in pg_type:
            return sa_type
    return cast(type[TypeEngine[object]], String)


def sa_to_python(sa_type: TypeEngine[object]) -> type[object]:
    type_str = str(sa_type).lower()
    for key, py_type in SA_TO_PYTHON.items():
        if key in type_str:
            return py_type
    return str
