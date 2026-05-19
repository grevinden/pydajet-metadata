"""Маппинг типов PostgreSQL → SQLAlchemy → Python."""

from datetime import datetime
from typing import Any

from sqlalchemy.types import Boolean, DateTime, Float, Integer, LargeBinary, String

PG_TO_SA = {
    "bytea": LargeBinary,
    "integer": Integer,
    "boolean": Boolean,
    "timestamp": DateTime,
    "datetime": DateTime,
    "datetime2": DateTime,
    "datetimeoffset": DateTime,
    "smalldatetime": DateTime,
    "date": DateTime,
    "time": DateTime,
    "character varying": String,
    "nvarchar": String,
    "nchar": String,
    "varchar": String,
    "char": String,
    "mvarchar": String,
    "text": String,
    "ntext": String,
    "uniqueidentifier": String,
    "numeric": Float,
    "decimal": Float,
    "money": Float,
    "smallmoney": Float,
    "double precision": Float,
    "real": Float,
    "float": Float,
    "bigint": Integer,
    "smallint": Integer,
    "tinyint": Integer,
    "bit": Boolean,
    "binary": LargeBinary,
    "varbinary": LargeBinary,
    "image": LargeBinary,
}

SA_TO_PYTHON = {
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


def pg_to_sqlalchemy(pg_type: str) -> type[Any]:
    pg_type = pg_type.lower()
    for key, sa_type in PG_TO_SA.items():
        if key in pg_type:
            return sa_type
    return String


def sa_to_python(sa_type: Any) -> type[Any]:
    type_str = str(sa_type).lower()
    for key, py_type in SA_TO_PYTHON.items():
        if key in type_str:
            return py_type
    return str
