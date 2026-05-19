"""Подключение к БД и управление транзакциями."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, List
from urllib.parse import quote_plus

from sqlalchemy import Column, MetaData, Table, create_engine, inspect
from sqlalchemy.engine import Engine

from pydajet_metadata._types import pg_to_sqlalchemy

if TYPE_CHECKING:
    from pydajet_metadata.protocols import ISession


class Session:  # Структурно соответствует ISession
    """Реализация ISession через SQLAlchemy Engine."""
    def __repr__(self) -> str:
        return f"Session(engine={self._engine.url.database!r})"

    def __init__(self, connection_string: str, data_source: str = "postgresql"):
        params = self._parse_cs(connection_string)
        url = self._build_engine_url(params, data_source.lower())
        self._engine = create_engine(url)
        self._inspector = inspect(self._engine)
        self._cache: dict[str, Table] = {}

    @staticmethod
    def _build_engine_url(params: dict[str, str], data_source: str) -> str:
        if data_source in ("postgresql", "postgres"):
            return (
                f"postgresql://{params['username']}:{params['password']}"
                f"@{params['host']}:{params.get('port', 5432)}/{params['database']}"
            )

        if data_source in ("sqlserver", "mssql"):
            driver = params.get("driver", "ODBC Driver 18 for SQL Server")
            port = params.get("port", "1433")
            host = params.get("host") or params.get("server")
            if not host:
                raise ValueError("Server/Host is required for SQL Server connection strings")

            dsn = (
                f"DRIVER={driver};SERVER={host},{port};DATABASE={params['database']};"
            )
            if params.get("trusted_connection", "").lower() in ("yes", "true", "sspi"):
                dsn += "Trusted_Connection=Yes;"
            else:
                dsn += f"UID={params['username']};PWD={params['password']};"

            return f"mssql+pyodbc:///?odbc_connect={quote_plus(dsn)}"

        raise ValueError(
            "Unknown data_source. Use 'postgresql' or 'sqlserver'."
        )

    @staticmethod
    def _parse_cs(cs: str) -> dict[str, str]:
        result = {
            k.strip().lower(): v.strip()
            for k, v in (p.split("=", 1) for p in cs.split(";") if "=" in p)
        }
        if "server" in result and "host" not in result:
            result["host"] = result["server"]
        if "uid" in result and "username" not in result:
            result["username"] = result["uid"]
        if "pwd" in result and "password" not in result:
            result["password"] = result["pwd"]
        return result

    @property
    def engine(self) -> Engine:
        """Возвращает SQLAlchemy Engine, используемый сессией."""
        return self._engine

    def reflect_table(self, table_name: str) -> Table:
        """Возвращает SQLAlchemy Table по имени таблицы, с кэшированием схемы."""
        key = table_name.lower()
        if key not in self._cache:
            cols = self._inspector.get_columns(key)
            columns: List[Column[Any]] = [
                Column(c["name"].lower(), pg_to_sqlalchemy(str(c["type"]))) for c in cols
            ]
            self._cache[key] = Table(key, MetaData(), *columns)
        return self._cache[key]

    def get_pk(self, table_name: str) -> str:
        """Возвращает имя первичного ключа для таблицы. Если PK не определён, берёт первую колонку."""
        pk = self._inspector.get_pk_constraint(table_name.lower())
        if pk and pk.get("constrained_columns"):
            return pk["constrained_columns"][0].lower()
        return list(self.reflect_table(table_name).columns.keys())[0]

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """
        Контекстный менеджер транзакции.

        Использует SQLAlchemy Engine.begin() для автоматического
        управления commit/rollback и освобождения соединения.

        Yields:
            self: текущий экземпляр Session с активной транзакцией

        Raises:
            Exception: пробрасывает любые исключения после rollback
        """
        from sqlalchemy.exc import SQLAlchemyError

        with self._engine.begin() as conn:
            # Временно подменяем engine на connection для всех операций
            old_engine = self._engine

            # Используем object.__setattr__ для избежания рекурсии
            # (self._engine — property или __setattr__ может быть переопределён)
            object.__setattr__(self, "_engine", conn)

            try:
                yield self
            except SQLAlchemyError:
                # Явный rollback при ошибках БД
                raise
            except Exception:
                # Rollback при любых ошибках
                raise
            finally:
                # Гарантированное восстановление engine
                object.__setattr__(self, "_engine", old_engine)
                # conn закрывается автоматически при выходе из with

    @contextmanager
    def savepoint(self) -> Iterator[Session]:
        """Контекстный менеджер для создания savepoint внутри текущей транзакции."""
        connection = self._engine if hasattr(self._engine, "connect") else self._engine

        if hasattr(connection, "begin_nested"):
            trans = connection.begin_nested()
        else:
            raise RuntimeError(
                "Savepoint requires an active connection. "
                "Use within session.transaction() context."
            )

        try:
            yield self
            trans.commit()
        except Exception:
            trans.rollback()
            raise

    def close(self) -> None:
        self._engine.dispose()
