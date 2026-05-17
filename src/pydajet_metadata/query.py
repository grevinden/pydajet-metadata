"""Построитель запросов к таблицам 1С."""

from datetime import datetime
from typing import Any, Optional

from pydantic import validate_call
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.types import Boolean, DateTime, Float, Integer, LargeBinary, String
from typing_extensions import Literal

from pydajet_metadata._uuid import format_uuid, generate, to_1c
from pydajet_metadata.mapper import ColumnMapper


class Query:
    def __init__(
        self, session, table_name, column_map, pk="_idrref", owner_key="_idrref"
    ):
        self._session = session
        self._table = session.reflect_table(table_name)
        self._column_map = column_map
        self._reverse_map = {v.lower(): k for k, v in column_map.items()}
        self._pk = pk.lower()
        self._owner_key = owner_key.lower()
        self._where = []
        self._children: dict[str, "Query"] = {}
        self._mapper = ColumnMapper(self._table, column_map)

    def __getattr__(self, name: str):
        try:
            return self._mapper.get_db_column(name)
        except KeyError:
            raise AttributeError(f"Column '{name}' not found")

    def where(self, *conditions):
        self._where = list(conditions)
        return self

    # ─── Read ─────────────────────────────────────────

    def all(self) -> list[dict[str, Any]]:
        stmt = select(self._table)
        for c in self._where:
            stmt = stmt.where(c)
        with self._session.engine.connect() as conn:
            return [self._row_to_dict(r) for r in conn.execute(stmt).all()]

    def first(self) -> Optional[dict[str, Any]]:
        stmt = select(self._table).limit(1)
        for c in self._where:
            stmt = stmt.where(c)
        with self._session.engine.connect() as conn:
            row = conn.execute(stmt).first()
            return self._row_to_dict(row) if row else None

    def count(self) -> int:
        stmt = select(func.count()).select_from(self._table)
        for c in self._where:
            stmt = stmt.where(c)
        with self._session.engine.connect() as conn:
            return conn.execute(stmt).scalar()

    # ─── Write ────────────────────────────────────────

    def insert(self, data: dict[str, Any], extra: dict[str, Any] = None) -> str:
        new_uuid = generate()
        db = self._human_to_db(data)
        db[self._pk] = to_1c(new_uuid)

        if extra:
            for k, v in extra.items():
                if isinstance(v, str) and len(v.replace("-", "")) == 32:
                    extra[k] = to_1c(v)
            db.update(extra)

        self._fill_defaults(db)

        stmt = insert(self._table).values(**db)
        with self._session.engine.begin() as conn:
            conn.execute(stmt)

        return format_uuid(new_uuid)

    def update(self, record_id: str, data: dict[str, Any]) -> bool:
        db = self._human_to_db(data)
        stmt = (
            update(self._table)
            .where(self._table.c[self._pk] == to_1c(record_id))
            .values(**db)
        )
        with self._session.engine.begin() as conn:
            return conn.execute(stmt).rowcount > 0

    def delete(self, record_id: str) -> bool:
        stmt = delete(self._table).where(self._table.c[self._pk] == to_1c(record_id))
        with self._session.engine.begin() as conn:
            return conn.execute(stmt).rowcount > 0

    # ─── Internal ─────────────────────────────────────

    def _row_to_dict(self, row):
        return self._mapper.db_to_human(row)

    def _human_to_db(self, data):
        return self._mapper.human_to_db(data)

    def _fill_defaults(self, db: dict):
        for col in self._table.columns:
            name = col.name.lower()
            if name not in db:
                d = self._default(col)
                if d is not None:
                    db[name] = d

    def _default(self, col) -> Any:
        name = col.name.lower()
        if name == "_version":
            return 0
        if name == "_marked":
            return False
        if name == "_posted":
            return True
        if name == "_date_time":
            return datetime.now()
        if name == "_number":
            return ""
        if name == "_keyfield":
            return to_1c(generate())
        if name.endswith("_rref"):
            return b"\x00" * 16
        if name.endswith("_rtref"):
            return b"\x00" * 4
        if name.endswith("_type"):
            return b"\x00" * 1
        if isinstance(col.type, String):
            return ""
        if isinstance(col.type, Boolean):
            return False
        if isinstance(col.type, (Integer, Float)):
            return 0
        if isinstance(col.type, LargeBinary):
            return b"\x00" * 16
        if isinstance(col.type, DateTime):
            return datetime.now()
        return None

    def _is_binary(self, col_name: str) -> bool:
        return col_name in self._table.c and isinstance(
            self._table.c[col_name].type, LargeBinary
        )

    @validate_call
    def lock(
        self,
        mode: Literal["exclusive", "shared"] = "exclusive",
        row_id: str = None,
        nowait: bool = False,
    ) -> None:
        """
        Накладывает блокировку на таблицу или конкретную запись.

        Args:
            mode: 'shared' (разделяемая) или 'exclusive' (эксклюзивная)
            row_id: UUID записи для блокировки строки (None — вся таблица)
            nowait: True — ошибка при занятой блокировке, False — ожидание

        Raises:
            OperationalError: если nowait=True и блокировка занята
        """
        if row_id is not None:
            # Блокировка строки через SELECT ... FOR UPDATE
            pk_col = self._table.c[self._pk]
            stmt = select(self._table).where(pk_col == to_1c(row_id))
            if mode == "shared":
                stmt = stmt.with_for_update(read=True, nowait=nowait)
            else:
                stmt = stmt.with_for_update(nowait=nowait)
            with self._session.engine.connect() as conn:
                conn.execute(stmt)
        else:
            # Блокировка всей таблицы через LOCK TABLE
            # Безопасное экранирование идентификатора таблицы
            dialect = self._session.engine.dialect
            safe_table = dialect.identifier_preparer.quote_identifier(self._table.name)
            lock_mode_sql = "SHARE" if mode == "shared" else "EXCLUSIVE"
            sql = f"LOCK TABLE {safe_table} IN {lock_mode_sql} MODE"
            if nowait:
                sql += " NOWAIT"
            with self._session.engine.begin() as conn:
                conn.execute(text(sql))
