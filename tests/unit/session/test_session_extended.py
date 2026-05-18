"""Расширенные тесты для Session - покрытие транзакций, savepoint и edge cases."""

import pytest
from unittest.mock import MagicMock, patch, call
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from pydajet_metadata.session import Session


class TestSessionParseCS:
    """Тесты парсинга строки подключения."""

    def test_parse_cs_with_spaces_around_equals(self):
        """Обработка пробелов вокруг знака '='."""
        session = Session.__new__(Session)
        cs = "Host = localhost ; Port = 5432 ; Database = TestDB"
        result = session._parse_cs(cs)
        assert result == {
            'host': 'localhost',
            'port': '5432',
            'database': 'TestDB',
        }

    def test_parse_cs_with_spaces_around_values(self):
        """Обработка пробелов вокруг значений."""
        session = Session.__new__(Session)
        cs = "Host=localhost ; Port=5432 ; Database=Test DB ; Username= user ; Password= pass "
        result = session._parse_cs(cs)
        assert result == {
            'host': 'localhost',
            'port': '5432',
            'database': 'Test DB',
            'username': 'user',
            'password': 'pass',
        }

    def test_parse_cs_missing_equals_ignored(self):
        """Пары без '=' игнорируются."""
        session = Session.__new__(Session)
        cs = "Host=localhost;InvalidPart;Port=5432"
        result = session._parse_cs(cs)
        assert result == {'host': 'localhost', 'port': '5432'}

    def test_parse_cs_empty_value(self):
        """Пустое значение после '='."""
        session = Session.__new__(Session)
        cs = "Host=localhost;Password=;Port=5432"
        result = session._parse_cs(cs)
        assert result == {'host': 'localhost', 'password': '', 'port': '5432'}

    def test_parse_cs_duplicate_keys_last_wins(self):
        """При дублировании ключей последнее значение побеждает."""
        session = Session.__new__(Session)
        cs = "Host=first;Host=second;Port=5432"
        result = session._parse_cs(cs)
        assert result == {'host': 'second', 'port': '5432'}

    def test_parse_cs_mixed_case_keys(self):
        """Ключи в разном регистре приводятся к нижнему."""
        session = Session.__new__(Session)
        cs = "HOST=server;host=override;Port=5432;PORT=5433"
        result = session._parse_cs(cs)
        assert result == {'host': 'override', 'port': '5433'}


class TestSessionReflectTable:
    """Тесты рефлексии таблиц."""

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_reflect_table_caches_result(self, mock_engine, mock_inspect):
        """Таблица кэшируется после первого отражения."""
        mock_inspector = MagicMock()
        mock_inspector.get_columns.return_value = [
            {'name': '_IDRRef', 'type': 'UUID'},
            {'name': '_Description', 'type': 'VARCHAR(150)'},
        ]
        mock_inspect.return_value = mock_inspector

        session = Session("Host=localhost;Database=test;Username=u;Password=p;")
        
        table1 = session.reflect_table("_Reference53")
        table2 = session.reflect_table("_Reference53")
        table3 = session.reflect_table("_REFERENCE53")  # регистр не важен

        assert table1 is table2 is table3
        mock_inspector.get_columns.assert_called_once()

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_reflect_table_uses_pg_to_sqlalchemy(self, mock_engine, mock_inspect):
        """Типы PostgreSQL конвертируются через pg_to_sqlalchemy."""
        mock_inspector = MagicMock()
        mock_inspector.get_columns.return_value = [
            {'name': '_IDRRef', 'type': 'bytea'},
            {'name': '_Version', 'type': 'integer'},
            {'name': '_Description', 'type': 'varchar(150)'},
        ]
        mock_inspect.return_value = mock_inspector

        with patch('pydajet_metadata.session.pg_to_sqlalchemy') as mock_converter:
            mock_converter.return_value = MagicMock()
            session = Session("Host=localhost;Database=test;Username=u;Password=p;")
            session.reflect_table("_Reference53")

            assert mock_converter.call_count == 3
            mock_converter.assert_any_call('bytea')
            mock_converter.assert_any_call('integer')
            mock_converter.assert_any_call('varchar(150)')


class TestSessionGetPK:
    """Тесты получения первичного ключа."""

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_get_pk_from_inspector(self, mock_engine, mock_inspect):
        """Получение PK из inspector.get_pk_constraint."""
        mock_inspector = MagicMock()
        mock_inspector.get_pk_constraint.return_value = {
            'constrained_columns': ['_IDRRef']
        }
        mock_inspect.return_value = mock_inspector

        session = Session("Host=localhost;Database=test;Username=u;Password=p;")
        pk = session.get_pk("_Reference53")

        assert pk == '_idrref'  # приводится к нижнему регистру

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_get_pk_fallback_to_first_column(self, mock_engine, mock_inspect):
        """Fallback на первую колонку, если PK не найден."""
        mock_inspector = MagicMock()
        mock_inspector.get_pk_constraint.return_value = {}
        mock_inspector.get_columns.return_value = [
            {'name': '_Description', 'type': 'varchar'},
            {'name': '_IDRRef', 'type': 'bytea'},
        ]
        mock_inspect.return_value = mock_inspector

        session = Session("Host=localhost;Database=test;Username=u;Password=p;")
        pk = session.get_pk("_Reference53")

        assert pk == '_description'  # первая колонка в нижнем регистре


class TestSessionTransaction:
    """Тесты транзакций."""

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_transaction_context_manager(self, mock_engine, mock_inspect):
        """Контекстный менеджер транзакции корректно управляет соединением."""
        mock_conn = MagicMock()
        mock_engine.return_value.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.return_value.begin.return_value.__exit__ = MagicMock(return_value=False)

        session = Session("Host=localhost;Database=test;Username=u;Password=p;")
        original_engine = session._engine

        with session.transaction() as s:
            assert s._engine is mock_conn
            assert s is session

        # После выхода engine восстанавливается
        assert session._engine is original_engine

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_transaction_rollback_on_exception(self, mock_engine, mock_inspect):
        """Исключение внутри транзакции вызывает rollback."""
        mock_conn = MagicMock()
        mock_engine.return_value.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.return_value.begin.return_value.__exit__ = MagicMock(return_value=False)

        session = Session("Host=localhost;Database=test;Username=u;Password=p;")

        with pytest.raises(ValueError):
            with session.transaction():
                raise ValueError("Test error")

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_transaction_sqlalchemy_error_not_swallowed(self, mock_engine, mock_inspect):
        """SQLAlchemyError пробрасывается наружу."""
        mock_conn = MagicMock()
        mock_engine.return_value.begin.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.return_value.begin.return_value.__exit__ = MagicMock(return_value=False)

        session = Session("Host=localhost;Database=test;Username=u;Password=p;")

        with pytest.raises(SQLAlchemyError):
            with session.transaction():
                raise SQLAlchemyError("DB error")


class TestSessionSavepoint:
    """Тесты savepoint для вложенных транзакций."""

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_savepoint_success(self, mock_engine, mock_inspect):
        """Успешный savepoint коммитит изменения."""
        mock_conn = MagicMock()
        mock_nested = MagicMock()
        mock_conn.begin_nested.return_value = mock_nested

        # Имитируем, что _engine уже является connection (внутри transaction)
        session = Session.__new__(Session)
        session._engine = mock_conn

        with session.savepoint():
            pass  # успешное выполнение

        mock_nested.commit.assert_called_once()
        mock_nested.rollback.assert_not_called()

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_savepoint_rollback_on_exception(self, mock_engine, mock_inspect):
        """Исключение внутри savepoint вызывает rollback."""
        mock_conn = MagicMock()
        mock_nested = MagicMock()
        mock_conn.begin_nested.return_value = mock_nested

        session = Session.__new__(Session)
        session._engine = mock_conn

        with pytest.raises(RuntimeError):
            with session.savepoint():
                raise RuntimeError("Test error")

        mock_nested.rollback.assert_called_once()
        mock_nested.commit.assert_not_called()

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_savepoint_requires_active_connection(self, mock_engine, mock_inspect):
        """Savepoint требует активного соединения."""
        mock_engine_no_begin_nested = MagicMock()
        delattr(mock_engine_no_begin_nested, 'begin_nested')

        session = Session.__new__(Session)
        session._engine = mock_engine_no_begin_nested

        with pytest.raises(RuntimeError, match="Savepoint requires an active connection"):
            with session.savepoint():
                pass


class TestSessionClose:
    """Тесты закрытия сессии."""

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_close_disposes_engine(self, mock_engine, mock_inspect):
        """Метод close() вызывает dispose() у engine."""
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance

        session = Session("Host=localhost;Database=test;Username=u;Password=p;")
        session.close()

        mock_engine_instance.dispose.assert_called_once()

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_close_idempotent(self, mock_engine, mock_inspect):
        """Многократный вызов close() не вызывает ошибок."""
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance

        session = Session("Host=localhost;Database=test;Username=u;Password=p;")
        session.close()
        session.close()  # второй вызов

        assert mock_engine_instance.dispose.call_count == 2


class TestSessionEdgeCases:
    """Тесты граничных случаев."""

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_session_repr(self, mock_engine, mock_inspect):
        """__repr__ возвращает информативную строку."""
        mock_engine_instance = MagicMock()
        mock_engine_instance.url.database = 'TestDB'
        mock_engine.return_value = mock_engine_instance

        session = Session("Host=localhost;Database=TestDB;Username=u;Password=p;")
        repr_str = repr(session)

        assert "Session" in repr_str
        assert "TestDB" in repr_str

    @patch('pydajet_metadata.session.inspect')
    @patch('pydajet_metadata.session.create_engine')
    def test_session_engine_property(self, mock_engine, mock_inspect):
        """Свойство engine возвращает внутренний _engine."""
        mock_engine_instance = MagicMock()
        mock_engine.return_value = mock_engine_instance

        session = Session("Host=localhost;Database=test;Username=u;Password=p;")
        
        assert session.engine is session._engine
