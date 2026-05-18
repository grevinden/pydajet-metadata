"""Подключение к БД и управление транзакциями."""

from contextlib import contextmanager

from sqlalchemy import Column, MetaData, Table, create_engine, inspect
from sqlalchemy.engine import Engine

from pydajet_metadata._types import pg_to_sqlalchemy


class Session:
    def __repr__(self) -> str:
        return f"Session(engine={self._engine.url.database!r})"

    def __init__(self, connection_string: str):
        params = self._parse_cs(connection_string)
        url = (
            f"postgresql://{params['username']}:{params['password']}"
            f"@{params['host']}:{params.get('port', 5432)}/{params['database']}"
        )
        self._engine = create_engine(url)
        self._inspector = inspect(self._engine)
        self._cache: dict[str, Table] = {}

    @staticmethod
    def _parse_cs(cs: str) -> dict[str, str]:
        return dict(
            (k.strip().lower(), v.strip())
            for k, v in (p.split("=", 1) for p in cs.split(";") if "=" in p)
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    def reflect_table(self, table_name: str) -> Table:
        key = table_name.lower()
        if key not in self._cache:
            cols = self._inspector.get_columns(key)
            columns = [
                Column(c["name"], pg_to_sqlalchemy(str(c["type"]))) for c in cols
            ]
            self._cache[key] = Table(key, MetaData(), *columns)
        return self._cache[key]

    def get_pk(self, table_name: str) -> str:
        pk = self._inspector.get_pk_constraint(table_name.lower())
        if pk and pk.get("constrained_columns"):
            return pk["constrained_columns"][0]
        return list(self.reflect_table(table_name).columns.keys())[0]

    @contextmanager
    def transaction(self):
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
    def savepoint(self):
        """
        Контекстный менеджер savepoint для вложенных транзакций.

        Автоматически создаёт точку сохранения при входе
        и откатывает/фиксирует её при выходе.
        """
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

    def close(self):
        self._engine.dispose()
