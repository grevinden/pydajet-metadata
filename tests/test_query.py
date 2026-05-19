"""Тесты Query builder."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, MetaData, Table
from sqlalchemy.types import Boolean, DateTime, Integer, LargeBinary, String

from pydajet_metadata._uuid import to_1c
from pydajet_metadata.exceptions import VersionConflictError
from pydajet_metadata.query import Query


class TestQuery:
    """Тесты построителя запросов."""

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.engine = MagicMock()
        session.reflect_table = MagicMock()
        return session

    @pytest.fixture
    def mock_table(self):
        metadata = MetaData()
        return Table(
            "_reference53",
            metadata,
            Column("_idrref", LargeBinary),
            Column("_version", Integer),
            Column("_marked", Boolean),
            Column("_description", String),
            Column("_code", String),
            Column("_fld56", String),
            Column("_fld57", DateTime),
            Column("_fld58", String),
            Column("_predefinedid", LargeBinary),
        )

    @pytest.fixture
    def query(self, mock_session, mock_table, sample_column_map):
        mock_session.reflect_table.return_value = mock_table
        return Query(mock_session, "_reference53", sample_column_map)

    def test_column_access_by_human_name(self, query):
        col = query.Наименование
        assert col.name == "_description"

    def test_column_access_invalid(self, query):
        with pytest.raises(AttributeError):
            _ = query.НесуществующаяКолонка

    def test_row_to_dict(self, query, sample_row_data):
        """Проверяет конвертацию строки БД в словарь с человеческими именами."""
        mock_row = MagicMock()

        def mock_getattr(instance, name):
            return sample_row_data.get(name)

        type(mock_row).__getattr__ = mock_getattr
        mock_row._mapping = sample_row_data

        with patch.object(query, "_row_to_dict", wraps=query._row_to_dict) as wrapped:
            result = query._row_to_dict(mock_row)

        assert result["Наименование"] == "Тестовый алгоритм"
        assert result["Код"] == "001"
        assert result["ТекстАлгоритма"] == 'Сообщить("Привет");'
        assert "5000289c-66b6-fadf-11f1-4e880e761abe" == result["Ссылка"]

    def test_human_to_db(self, query):
        data = {
            "Наименование": "Тест",
            "Код": "001",
            "ТекстАлгоритма": 'Сообщить("Привет");',
        }
        result = query._human_to_db(data)
        assert result["_description"] == "Тест"
        assert result["_code"] == "001"
        assert result["_fld56"] == 'Сообщить("Привет");'

    def test_default_values(self, query):
        for col in query._table.columns:
            default = query._default(col)
            if col.name == "_version":
                assert default == 0
            elif col.name == "_marked":
                assert default == False

    def test_fill_defaults(self, query):
        db = {"_description": "Тест"}
        query._fill_defaults(db)
        assert db["_version"] == 0
        assert db["_marked"] == False

    @patch("pydajet_metadata.query.insert")
    def test_insert(self, mock_insert, query):
        mock_insert.return_value.values.return_value = MagicMock()
        query._session.engine.begin = MagicMock()
        query._session.engine.begin.return_value.__enter__ = MagicMock()

        result = query.insert({"Наименование": "Новый"})
        assert result is not None
        assert len(result) == 36  # UUID с дефисами


class TestQueryLocks:
    """Тесты блокировок."""

    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.engine = MagicMock()
        session.reflect_table = MagicMock()
        return session

    @pytest.fixture
    def mock_table(self):
        metadata = MetaData()
        return Table(
            "_reference53",
            metadata,
            Column("_idrref", LargeBinary),
            Column("_version", Integer),
            Column("_marked", Boolean),
            Column("_description", String),
            Column("_code", String),
            Column("_fld56", String),
            Column("_fld57", DateTime),
            Column("_fld58", String),
            Column("_predefinedid", LargeBinary),
        )

    @pytest.fixture
    def query(self, mock_session, mock_table, sample_column_map):
        mock_session.reflect_table.return_value = mock_table
        return Query(mock_session, "_reference53", sample_column_map)

    # --- Тесты блокировки строки ---

    def test_lock_row_exclusive(self, query):
        """Эксклюзивная блокировка строки: проверяем, что это обычный FOR UPDATE."""
        row_id = "9c280050-b666-dffa-11f1-4e880e761abe"

        with patch.object(query._session, "engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn

            query.lock(mode="exclusive", row_id=row_id)

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args[0][0]
            # Проверяем, что это действительно SELECT ... FOR UPDATE
            assert call_args._for_update_arg is not None
            assert call_args._for_update_arg.read is False
            assert call_args._for_update_arg.nowait is False

    def test_lock_row_share(self, query):
        """Разделяемая блокировка строки: FOR UPDATE с read=True (FOR SHARE)."""
        row_id = "9c280050-b666-dffa-11f1-4e880e761abe"

        with patch.object(query._session, "engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn

            query.lock(mode="shared", row_id=row_id)

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args[0][0]
            # Проверяем, что это FOR SHARE (реализуется как FOR UPDATE с read=True)
            assert call_args._for_update_arg is not None
            assert call_args._for_update_arg.read is True
            assert call_args._for_update_arg.nowait is False

    def test_lock_row_nowait(self, query):
        """Блокировка строки с NOWAIT."""
        row_id = "9c280050-b666-dffa-11f1-4e880e761abe"

        with patch.object(query._session, "engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn

            query.lock(mode="exclusive", row_id=row_id, nowait=True)

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args[0][0]
            # Проверяем, что установлен флаг nowait
            assert call_args._for_update_arg is not None
            assert call_args._for_update_arg.nowait is True

    # --- Тесты блокировки таблицы (здесь SQL генерируется через text(), можно проверять строку) ---

    def test_lock_table_exclusive(self, query):
        """Эксклюзивная блокировка таблицы: LOCK TABLE ... IN EXCLUSIVE MODE."""
        with patch.object(query._session, "engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.begin.return_value.__enter__.return_value = mock_conn

            query.lock(mode="exclusive")

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args[0][0]
            sql_str = str(call_args)
            assert "LOCK TABLE" in sql_str
            assert "EXCLUSIVE" in sql_str

    def test_lock_table_share(self, query):
        """Разделяемая блокировка таблицы: LOCK TABLE ... IN SHARE MODE."""
        with patch.object(query._session, "engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.begin.return_value.__enter__.return_value = mock_conn

            query.lock(mode="shared")

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args[0][0]
            sql_str = str(call_args)
            assert "LOCK TABLE" in sql_str
            assert "SHARE" in sql_str

    def test_lock_table_nowait(self, query):
        """Блокировка таблицы с NOWAIT."""
        with patch.object(query._session, "engine") as mock_engine:
            mock_conn = MagicMock()
            mock_engine.begin.return_value.__enter__.return_value = mock_conn

            query.lock(mode="exclusive", nowait=True)

            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args[0][0]
            sql_str = str(call_args)
            assert "NOWAIT" in sql_str

    def test_pk_condition_falls_back_to_text(self, mock_session, mock_table, sample_column_map):
        mock_session.reflect_table.return_value = mock_table
        query = Query(mock_session, "_reference53", sample_column_map, pk="_missing")
        condition = query._pk_condition("9c280050-b666-dffa-11f1-4e880e761abe")
        assert "_missing" in str(condition)

    def test_versioned_update_and_conflict(self, query):
        query._mapper.human_to_db = MagicMock(return_value={"_description": "Обновлённый"})
        query._get_current_version = MagicMock(return_value=1)
        query._session.engine.begin.return_value.__enter__.return_value.execute.return_value.rowcount = 1

        assert query.Изменить(
            "9c280050-b666-dffa-11f1-4e880e761abe",
            {"Наименование": "Обновлённый"},
            expected_version=1,
        )

        with pytest.raises(VersionConflictError):
            query.Изменить(
                "9c280050-b666-dffa-11f1-4e880e761abe",
                {"Наименование": "Обновлённый"},
                expected_version=2,
            )

    def test_safe_update_and_get_version(self, query):
        query._mapper.human_to_db = MagicMock(return_value={"_description": "Обновлённый"})
        query._get_current_version = MagicMock(return_value=2)
        query._session.engine.begin.return_value.__enter__.return_value.execute.return_value.rowcount = 1

        assert query.БезопасноеИзменить(
            "9c280050-b666-dffa-11f1-4e880e761abe",
            {"Наименование": "Обновлённый"},
        )
        assert query.ПолучитьВерсию("9c280050-b666-dffa-11f1-4e880e761abe") == 2
