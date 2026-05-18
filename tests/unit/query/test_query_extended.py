"""Расширенные тесты для Query - покрытие edge cases, валидации и внутренних методов."""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, call
from sqlalchemy import Column, MetaData, Table, select, func
from sqlalchemy.types import String, Integer, Boolean, DateTime, LargeBinary

from pydajet_metadata.query import Query
from pydajet_metadata.exceptions import VersionConflictError
from pydajet_metadata._uuid import generate, to_1c, format_uuid


class TestQueryInitialization:
    """Тесты инициализации Query."""

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_query_init_stores_params(self, mock_mapper_cls):
        """Query сохраняет параметры инициализации."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData(), Column('_IDRRef', String))
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper
        mock_mapper.human_names = ['Ссылка', 'Наименование']

        column_map = {'Ссылка': '_IDRRef', 'Наименование': '_Description'}
        
        query = Query(mock_session, '_Reference53', column_map, pk='_IDRRef', owner_key='_OwnerRRef')

        assert query._session is mock_session
        assert query._table is mock_table
        assert query._mapper is mock_mapper
        assert query._pk == '_idrref'  # к нижнему регистру
        assert query._owner_key == '_ownerrref'
        assert query._where == []
        assert query._children == {}

    def test_query_repr(self):
        """__repr__ возвращает информативную строку."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData(), Column('_IDRRef', String))
        mock_session.reflect_table.return_value = mock_table
        
        with patch('pydajet_metadata.query.ColumnMapper') as mock_mapper_cls:
            mock_mapper = MagicMock()
            mock_mapper.human_names = ['Ссылка', 'Наименование', 'Код']
            mock_mapper_cls.return_value = mock_mapper

            query = Query(mock_session, '_Reference53', {})
            repr_str = repr(query)

            assert '_Reference53' in repr_str
            assert '_idrref' in repr_str
            assert '3' in repr_str  # количество колонок


class TestQueryGetAttr:
    """Тесты динамического доступа к колонкам через __getattr__."""

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_getattr_returns_db_column(self, mock_mapper_cls):
        """Доступ к человеческому имени возвращает DB колонку."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData(), Column('_Description', String))
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper.get_db_column.return_value = mock_table.c['_Description']
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {'Наименование': '_Description'})
        
        result = query.Наименование
        
        assert result is mock_table.c['_Description']
        mock_mapper.get_db_column.assert_called_once_with('Наименование')

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_getattr_raises_on_unknown_column(self, mock_mapper_cls):
        """Неизвестная колонка вызывает AttributeError."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper.get_db_column.side_effect = KeyError('Неизвестная')
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {})
        
        with pytest.raises(AttributeError, match="Column 'Неизвестная' not found"):
            _ = query.Неизвестная


class TestQueryWhere:
    """Тесты метода where()."""

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_where_accepts_multiple_conditions(self, mock_mapper_cls):
        """where() принимает несколько условий и возвращает self."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {})
        cond1 = MagicMock()
        cond2 = MagicMock()
        
        result = query.where(cond1, cond2)
        
        assert result is query
        assert query._where == [cond1, cond2]

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_where_overwrites_previous_conditions(self, mock_mapper_cls):
        """Повторный вызов where() заменяет предыдущие условия."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {})
        
        query.where(MagicMock())
        query.where(MagicMock(), MagicMock())
        
        assert len(query._where) == 2


class TestQueryReadMethods:
    """Тесты методов чтения: all(), first(), count()."""

    @patch('pydajet_metadata.query.ColumnMapper')
    @patch('pydajet_metadata.query.select')
    def test_all_executes_select_with_where(self, mock_select, mock_mapper_cls):
        """all() выполняет SELECT с применёнными условиями where."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        mock_session.engine.connect.return_value.__enter__.return_value.execute.return_value.all.return_value = []
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {})
        mock_condition = MagicMock()
        query.where(mock_condition)
        
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.where.return_value = mock_stmt
        
        query.all()
        
        mock_select.assert_called_once_with(mock_table)
        mock_stmt.where.assert_called_once_with(mock_condition)

    @patch('pydajet_metadata.query.ColumnMapper')
    @patch('pydajet_metadata.query.select')
    def test_first_limits_to_one_row(self, mock_select, mock_mapper_cls):
        """first() добавляет LIMIT 1 к запросу."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        mock_session.engine.connect.return_value.__enter__.return_value.execute.return_value.first.return_value = None
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {})
        
        mock_stmt = MagicMock()
        mock_select.return_value = mock_stmt
        mock_stmt.limit.return_value = mock_stmt
        
        result = query.first()
        
        assert result is None
        mock_stmt.limit.assert_called_once_with(1)

    @patch('pydajet_metadata.query.ColumnMapper')
    @patch('pydajet_metadata.query.func')
    @patch('pydajet_metadata.query.select')
    def test_count_uses_func_count(self, mock_select, mock_func, mock_mapper_cls):
        """count() использует func.count() для подсчёта записей."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        mock_session.engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = 42
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper
        mock_func.count.return_value = 'COUNT(*)'

        query = Query(mock_session, '_Reference53', {})
        
        result = query.count()
        
        assert result == 42
        mock_func.count.assert_called_once()


class TestQueryWriteMethods:
    """Тесты методов записи: insert(), update(), delete()."""

    @patch('pydajet_metadata.query.ColumnMapper')
    @patch('pydajet_metadata.query.insert')
    @patch('pydajet_metadata.query.to_1c')
    @patch('pydajet_metadata.query.generate')
    def test_insert_generates_uuid_and_converts(self, mock_generate, mock_to_1c, mock_insert, mock_mapper_cls):
        """insert() генерирует UUID и конвертирует его в формат 1С."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper.human_to_db.return_value = {'_Description': 'Test'}
        mock_mapper_cls.return_value = mock_mapper

        new_uuid = generate()
        mock_generate.return_value = new_uuid
        mock_to_1c.return_value = b'\x00' * 16

        query = Query(mock_session, '_Reference53', {'Наименование': '_Description'}, pk='_IDRRef')
        
        result = query.insert({'Наименование': 'Test'})
        
        assert result == format_uuid(new_uuid)
        mock_to_1c.assert_called_once_with(new_uuid)
        mock_insert.assert_called_once()

    @patch('pydajet_metadata.query.ColumnMapper')
    @patch('pydajet_metadata.query.update')
    @patch('pydajet_metadata.query.to_1c')
    def test_update_returns_bool_based_on_rowcount(self, mock_to_1c, mock_update, mock_mapper_cls):
        """update() возвращает True, если затронута хотя бы одна строка."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper.human_to_db.return_value = {'_Description': 'Updated'}
        mock_mapper_cls.return_value = mock_mapper

        mock_to_1c.return_value = b'\x00' * 16
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_conn.execute.return_value = mock_result
        mock_session.engine.begin.return_value.__enter__.return_value = mock_conn

        query = Query(mock_session, '_Reference53', {}, pk='_IDRRef')
        
        result = query.update('5000289c-66b6-fadf-11f1-4e880e761abe', {'Наименование': 'Updated'})
        
        assert result is True

    @patch('pydajet_metadata.query.ColumnMapper')
    @patch('pydajet_metadata.query.delete')
    @patch('pydajet_metadata.query.to_1c')
    def test_delete_returns_false_when_not_found(self, mock_to_1c, mock_delete, mock_mapper_cls):
        """delete() возвращает False, если запись не найдена."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper

        mock_to_1c.return_value = b'\x00' * 16
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_conn.execute.return_value = mock_result
        mock_session.engine.begin.return_value.__enter__.return_value = mock_conn

        query = Query(mock_session, '_Reference53', {}, pk='_IDRRef')
        
        result = query.delete('5000289c-66b6-fadf-11f1-4e880e761abe')
        
        assert result is False


class TestQueryInternalMethods:
    """Тесты внутренних методов: _row_to_dict, _human_to_db, _fill_defaults."""

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_row_to_dict_delegates_to_mapper(self, mock_mapper_cls):
        """_row_to_dict делегирует конвертацию мапперу."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper.db_to_human.return_value = {'Наименование': 'Test'}
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {})
        mock_row = MagicMock()
        
        result = query._row_to_dict(mock_row)
        
        assert result == {'Наименование': 'Test'}
        mock_mapper.db_to_human.assert_called_once_with(mock_row)

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_human_to_db_delegates_to_mapper(self, mock_mapper_cls):
        """_human_to_db делегирует конвертацию мапперу."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper.human_to_db.return_value = {'_Description': 'Test'}
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {})
        
        result = query._human_to_db({'Наименование': 'Test'})
        
        assert result == {'_Description': 'Test'}
        mock_mapper.human_to_db.assert_called_once_with({'Наименование': 'Test'})

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_fill_defaults_sets_version_and_marked(self, mock_mapper_cls):
        """_fill_defaults устанавливает значения по умолчанию для системных полей."""
        mock_session = MagicMock()
        mock_table = Table(
            '_Reference53', MetaData(),
            Column('_version', Integer),
            Column('_marked', Boolean),
            Column('_posted', Boolean),
        )
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {})
        db_data = {}
        
        query._fill_defaults(db_data)
        
        assert db_data['_version'] == 0
        assert db_data['_marked'] is False
        assert db_data['_posted'] is True


class TestQueryLock:
    """Тесты метода lock() для блокировок."""

    @patch('pydajet_metadata.query.ColumnMapper')
    @patch('pydajet_metadata.query.to_1c')
    def test_lock_row_exclusive(self, mock_to_1c, mock_mapper_cls):
        """Блокировка строки в эксклюзивном режиме."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper
        mock_to_1c.return_value = b'\x00' * 16

        query = Query(mock_session, '_Reference53', {}, pk='_IDRRef')
        mock_conn = MagicMock()
        mock_session.engine.connect.return_value.__enter__.return_value = mock_conn

        query.lock(mode='exclusive', row_id='5000289c-66b6-fadf-11f1-4e880e761abe')
        
        mock_conn.execute.assert_called_once()

    @patch('pydajet_metadata.query.ColumnMapper')
    @patch('pydajet_metadata.query.text')
    def test_lock_table_shared_nowait(self, mock_text, mock_mapper_cls):
        """Блокировка всей таблицы в режиме shared с nowait."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper
        
        mock_dialect = MagicMock()
        mock_dialect.identifier_preparer.quote_identifier.return_value = '"_Reference53"'
        mock_session.engine.dialect = mock_dialect

        query = Query(mock_session, '_Reference53', {})
        mock_conn = MagicMock()
        mock_session.engine.begin.return_value.__enter__.return_value = mock_conn

        query.lock(mode='shared', nowait=True)
        
        mock_text.assert_called_once()
        call_args = mock_text.call_args[0][0]
        assert 'LOCK TABLE' in call_args
        assert 'IN SHARE MODE' in call_args
        assert 'NOWAIT' in call_args


class TestQueryVersionHandling:
    """Тесты обработки версий для оптимистичных блокировок."""

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_get_current_version_when_column_exists(self, mock_mapper_cls):
        """Получение версии, когда колонка _version существует."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData(), Column('_version', Integer))
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper

        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 5
        mock_session.engine.connect.return_value.__enter__.return_value = mock_conn

        query = Query(mock_session, '_Reference53', {}, pk='_IDRRef')
        
        with patch('pydajet_metadata.query.to_1c') as mock_to_1c:
            mock_to_1c.return_value = b'\x00' * 16
            version = query._get_current_version('5000289c-66b6-fadf-11f1-4e880e761abe')
            
            assert version == 5

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_get_current_version_when_column_missing(self, mock_mapper_cls):
        """Получение версии возвращает 0, если колонки нет."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())  # без _version
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {}, pk='_IDRRef')
        
        version = query._get_current_version('any-uuid')
        
        assert version == 0

    @patch('pydajet_metadata.query.ColumnMapper')
    @patch('pydajet_metadata.query.to_1c')
    def test_изменить_with_version_conflict(self, mock_to_1c, mock_mapper_cls):
        """Изменить() выбрасывает VersionConflictError при несовпадении версий."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData(), Column('_version', Integer))
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper.human_to_db.return_value = {}
        mock_mapper_cls.return_value = mock_mapper
        mock_to_1c.return_value = b'\x00' * 16

        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 10  # текущая версия
        mock_session.engine.connect.return_value.__enter__.return_value = mock_conn

        query = Query(mock_session, '_Reference53', {}, pk='_IDRRef')
        
        with pytest.raises(VersionConflictError) as exc_info:
            query.Изменить('uuid', {}, expected_version=5)
        
        assert 'expected version 5' in str(exc_info.value)
        assert 'actual version 10' in str(exc_info.value)

    @patch('pydajet_metadata.query.ColumnMapper')
    @patch('pydajet_metadata.query.to_1c')
    def test_изменить_increments_version(self, mock_to_1c, mock_mapper_cls):
        """Изменить() инкрементирует версию при успешном обновлении."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData(), Column('_version', Integer))
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper.human_to_db.return_value = {'_Description': 'New'}
        mock_mapper_cls.return_value = mock_mapper
        mock_to_1c.return_value = b'\x00' * 16

        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = 3  # текущая версия
        mock_session.engine.connect.return_value.__enter__.return_value = mock_conn
        mock_session.engine.begin.return_value.__enter__.return_value = mock_conn

        query = Query(mock_session, '_Reference53', {}, pk='_IDRRef')
        
        # Мокаем update чтобы проверить, что _version=4 передаётся
        with patch('pydajet_metadata.query.update') as mock_update_func:
            mock_result = MagicMock()
            mock_result.rowcount = 1
            mock_conn.execute.return_value = mock_result
            mock_update_func.return_value.where.return_value.values.return_value = MagicMock()
            
            query.Изменить('uuid', {'Наименование': 'New'})
            
            # Проверяем, что values() вызван с _version=4
            call_kwargs = mock_update_func.return_value.where.return_value.values.call_args[1]
            assert call_kwargs['_version'] == 4

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_безопасноеизменить_автоматически_получает_версию(self, mock_mapper_cls):
        """БезопасноеИзменить() автоматически получает текущую версию."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData(), Column('_version', Integer))
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {}, pk='_IDRRef')
        
        with patch.object(query, '_get_current_version') as mock_get_ver:
            mock_get_ver.return_value = 7
            with patch.object(query, 'Изменить') as mock_изменить:
                query.БезопасноеИзменить('uuid', {})
                
                mock_изменить.assert_called_once_with('uuid', {}, expected_version=7)

    @patch('pydajet_metadata.query.ColumnMapper')
    def test_получитьверсию_делегирование(self, mock_mapper_cls):
        """ПолучитьВерсию() делегирует вызов _get_current_version."""
        mock_session = MagicMock()
        mock_table = Table('_Reference53', MetaData())
        mock_session.reflect_table.return_value = mock_table
        
        mock_mapper = MagicMock()
        mock_mapper_cls.return_value = mock_mapper

        query = Query(mock_session, '_Reference53', {}, pk='_IDRRef')
        
        with patch.object(query, '_get_current_version') as mock_get_ver:
            mock_get_ver.return_value = 15
            result = query.ПолучитьВерсию('uuid')
            
            assert result == 15
            mock_get_ver.assert_called_once_with('uuid')
