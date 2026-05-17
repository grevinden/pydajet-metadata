"""Подключение к БД и управление транзакциями."""
from contextlib import contextmanager
from sqlalchemy import create_engine, inspect, MetaData, Table, Column
from sqlalchemy.engine import Engine

from pydajet_metadata._types import pg_to_sqlalchemy


class Session:
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
            for k, v in (p.split('=', 1) for p in cs.split(';') if '=' in p)
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    def reflect_table(self, table_name: str) -> Table:
        key = table_name.lower()
        if key not in self._cache:
            cols = self._inspector.get_columns(key)
            columns = [Column(c['name'], pg_to_sqlalchemy(str(c['type']))) for c in cols]
            self._cache[key] = Table(key, MetaData(), *columns)
        return self._cache[key]

    def get_pk(self, table_name: str) -> str:
        pk = self._inspector.get_pk_constraint(table_name.lower())
        if pk and pk.get('constrained_columns'):
            return pk['constrained_columns'][0]
        return list(self.reflect_table(table_name).columns.keys())[0]

    @contextmanager
    def transaction(self):
        connection = self._engine.connect()
        trans = connection.begin()
        old = self._engine
        self._engine = connection
        try:
            yield self
            trans.commit()
        except Exception:
            trans.rollback()
            raise
        finally:
            self._engine = old
            connection.close()

    @contextmanager
    def savepoint(self):
        connection = self._engine if hasattr(self._engine, 'connect') else self._engine
        trans = connection.begin_nested() if hasattr(connection, 'begin_nested') else None
        try:
            yield self
            if trans:
                trans.commit()
        except Exception:
            if trans:
                trans.rollback()
            raise

    def close(self):
        self._engine.dispose()
