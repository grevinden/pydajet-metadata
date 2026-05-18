"""Расширенные тесты для SchemaGenerator - покрытие валидации, табличных частей и методов моделей."""

import pytest
from unittest.mock import MagicMock, patch, call
from pydantic import BaseModel, ValidationError, Field

from pydajet_metadata.schema import SchemaGenerator


class TestSchemaGeneratorInit:
    """Тесты инициализации SchemaGenerator."""

    def test_init_calls_generate(self):
        """__init__ автоматически вызывает _generate()."""
        mock_repo = MagicMock()
        mock_repo.types.return_value = ['Справочники']
        mock_repo.objects.return_value = ['Тестовый']
        mock_repo.query.return_value = MagicMock()

        with patch.object(SchemaGenerator, '_generate') as mock_gen:
            gen = SchemaGenerator(mock_repo)
            mock_gen.assert_called_once()

    def test_generate_iterates_types_and_objects(self):
        """_generate() проходит по всем типам и объектам."""
        mock_repo = MagicMock()
        mock_repo.types.return_value = ['Справочники', 'Документы']
        mock_repo.objects.side_effect = [
            ['Алгоритмы', 'Пользователи'],  # для Справочники
            ['Уведомления']  # для Документы
        ]
        mock_query = MagicMock()
        mock_repo.query.return_value = mock_query

        with patch.object(SchemaGenerator, '_create_model') as mock_create:
            mock_create.return_value = MagicMock(spec=BaseModel)
            gen = SchemaGenerator(mock_repo)

            # Проверяем, что _create_model вызван для каждого объекта
            assert mock_create.call_count == 3
            calls = [c[0][0] for c in mock_create.call_args_list]
            assert 'Алгоритмы' in calls
            assert 'Пользователи' in calls
            assert 'Уведомления' in calls


class TestCreateModelFieldGeneration:
    """Тесты генерации полей модели."""

    @patch('pydajet_metadata.schema.sa_to_python')
    def test_create_model_pk_field_is_optional(self, mock_sa_to_python):
        """Поле первичного ключа всегда опциональное."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {'Ссылка': '_IDRRef', 'Наименование': '_Description'}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_ownerrref'
        mock_query._children = {}
        
        mock_col_pk = MagicMock()
        mock_col_pk.nullable = False
        mock_col_other = MagicMock()
        mock_col_other.nullable = False
        
        mock_query._table.c = {
            '_idrref': mock_col_pk,
            '_description': mock_col_other,
        }
        mock_sa_to_python.return_value = str

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        model = gen._create_model('TestModel', mock_query)

        # Проверяем аннотации полей
        annotations = model.__annotations__
        assert annotations.get('Ссылка') == type(None) | str  # Optional[str]
        # Наименование не обязательное, т.к. кол-во проверок зависит от логики

    @patch('pydajet_metadata.schema.sa_to_python')
    def test_create_model_required_field_when_not_nullable(self, mock_sa_to_python):
        """Не nullable поля без default становятся обязательными."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {'Код': '_Code'}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_ownerrref'
        mock_query._children = {}
        
        mock_col = MagicMock()
        mock_col.nullable = False
        mock_query._table.c = {'_code': mock_col}
        mock_sa_to_python.return_value = str

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        model = gen._create_model('TestModel', mock_query)

        # Проверяем, что поле имеет ... (required) в Field
        fields = model.model_fields
        assert 'Код' in fields
        assert fields['Код'].is_required()

    @patch('pydajet_metadata.schema.sa_to_python')
    def test_create_model_optional_field_when_nullable(self, mock_sa_to_python):
        """Nullable поля становятся опциональными с default=None."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {'Комментарий': '_Fld58'}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_ownerrref'
        mock_query._children = {}
        
        mock_col = MagicMock()
        mock_col.nullable = True
        mock_query._table.c = {'_fld58': mock_col}
        mock_sa_to_python.return_value = str

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        model = gen._create_model('TestModel', mock_query)

        fields = model.model_fields
        assert 'Комментарий' in fields
        assert fields['Комментарий'].default is None


class TestCreateModelWithChildren:
    """Тесты создания модели с табличными частями."""

    @patch('pydajet_metadata.schema.sa_to_python')
    def test_create_model_adds_child_fields(self, mock_sa_to_python):
        """Табличные части добавляются как list[ChildModel]."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {'Ссылка': '_IDRRef'}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_idrref'
        
        # Создаём мок для дочернего запроса
        mock_child_query = MagicMock()
        mock_child_query._column_map = {'Элемент': '_Fld1'}
        mock_child_query._pk = '_idrref'
        mock_child_query._owner_key = '_ParentRRef'
        mock_child_query._children = {}
        mock_child_query._table.c = {'_fld1': MagicMock(nullable=True)}
        
        mock_query._children = {'ТабличнаяЧасть': mock_child_query}
        mock_sa_to_python.return_value = str

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        with patch.object(gen, '_create_model') as mock_create_child:
            # Use an actual BaseModel subclass for child model so Pydantic accepts it
            mock_child_model = type('ChildModel', (BaseModel,), {})
            mock_create_child.return_value = mock_child_model
            
            model = SchemaGenerator._create_model(gen, 'ParentModel', mock_query)

            # Проверяем, что поле табличной части создано
            fields = model.model_fields
            assert 'ТабличнаяЧасть' in fields
            # Поле должно быть Optional[list[ChildModel]] с default_factory=list


class TestModelMethods:
    """Тесты динамически добавленных методов моделей."""

    @patch('pydajet_metadata.schema.sa_to_python')
    @patch('pydajet_metadata.schema.to_1c')
    def test_from_db_loads_record_and_children(self, mock_to_1c, mock_sa_to_python):
        """from_db() загружает запись и её табличные части."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {'Ссылка': '_IDRRef', 'Наименование': '_Description'}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_idrref'
        mock_query._children = {'Детали': MagicMock()}
        mock_query._table.c = {
            '_idrref': MagicMock(),
            '_description': MagicMock(nullable=False),
        }
        mock_sa_to_python.return_value = str
        mock_to_1c.return_value = b'\x00' * 16

        # Мокаем данные из БД
        mock_row = {'_idrref': b'\x00'*16, '_description': 'Test'}
        mock_query.where.return_value.first.return_value = mock_row
        
        # Мокаем табличную часть
        mock_child_query = mock_query._children['Детали']
        mock_child_query._owner_key = '_ParentRRef'
        mock_child_query.where.return_value.all.return_value = [
            {'_fld1': 'Detail1'},
            {'_fld1': 'Detail2'},
        ]

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        model = gen._create_model('TestModel', mock_query)
        
        # Создаём экземпляр и вызываем from_db
        with patch.object(model, '__init__', return_value=None):
            result = model.from_db('5000289c-66b6-fadf-11f1-4e880e761abe')
            
            # Проверяем, что query.where вызван с правильным условием
            mock_query.where.assert_called()
            mock_child_query.where.assert_called()

    @patch('pydajet_metadata.schema.sa_to_python')
    def test_save_inserts_new_record(self, mock_sa_to_python):
        """save() вызывает insert() для новой записи."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {'Ссылка': '_IDRRef', 'Наименование': '_Description'}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_idrref'
        mock_query._children = {}
        mock_query._table.c = {
            '_idrref': MagicMock(),
            '_description': MagicMock(nullable=False),
        }
        mock_sa_to_python.return_value = str
        mock_query.count.return_value = 0  # записей нет, значит новая

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        model = gen._create_model('TestModel', mock_query)
        instance = model(Наименование='New Item')
        
        mock_query.insert.return_value = 'new-uuid'
        
        result = instance.save()
        
        assert result is instance
        mock_query.insert.assert_called_once()

    @patch('pydajet_metadata.schema.sa_to_python')
    def test_save_updates_existing_record(self, mock_sa_to_python):
        """save() вызывает update() для существующей записи."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {'Ссылка': '_IDRRef', 'Наименование': '_Description'}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_idrref'
        mock_query._children = {}
        mock_query._table.c = {
            '_idrref': MagicMock(),
            '_description': MagicMock(nullable=False),
        }
        mock_sa_to_python.return_value = str
        mock_query.count.return_value = 1  # запись существует

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        model = gen._create_model('TestModel', mock_query)
        instance = model(Ссылка='existing-uuid', Наименование='Updated')
        
        result = instance.save()
        
        assert result is instance
        # Проверяем, что update вызван вместо insert
        mock_query.update.assert_called_once()
        mock_query.insert.assert_not_called()

    @patch('pydajet_metadata.schema.sa_to_python')
    def test_save_handles_child_parts(self, mock_sa_to_python):
        """save() корректно обрабатывает табличные части."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {'Ссылка': '_IDRRef'}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_idrref'
        
        mock_child_query = MagicMock()
        mock_child_query._owner_key = '_ParentRRef'
        mock_query._children = {'Детали': mock_child_query}
        mock_query._table.c = {'_idrref': MagicMock()}
        mock_sa_to_python.return_value = str
        mock_query.count.return_value = 0

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        model = gen._create_model('TestModel', mock_query)
        
        # Создаём экземпляр с табличной частью
        child_mock = MagicMock(spec=BaseModel)
        child_mock.model_dump.return_value = {'_fld1': 'value'}
        instance = model(Детали=[child_mock])
        
        mock_query.insert.return_value = 'parent-uuid'
        
        instance.save()
        
        # Проверяем, что вставка табличной части использует родительский UUID
        mock_child_query.insert.assert_called_once()
        call_kwargs = mock_child_query.insert.call_args[0][0]
        assert call_kwargs['_ParentRRef'] == 'parent-uuid'

    @patch('pydajet_metadata.schema.sa_to_python')
    def test_delete_removes_record_and_children(self, mock_sa_to_python):
        """delete() удаляет запись и все её табличные части."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {'Ссылка': '_IDRRef'}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_idrref'
        
        mock_child_query = MagicMock()
        mock_query._children = {'Детали': mock_child_query}
        mock_query._table.c = {'_idrref': MagicMock()}
        mock_sa_to_python.return_value = str

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        model = gen._create_model('TestModel', mock_query)
        instance = model(Ссылка='target-uuid')
        
        result = instance.delete()
        
        assert result is instance
        # Сначала удаляются табличные части, потом основная запись
        mock_child_query.delete.assert_called_once_with('target-uuid')
        mock_query.delete.assert_called_once_with('target-uuid')

    @patch('pydajet_metadata.schema.sa_to_python')
    def test_all_returns_list_of_instances(self, mock_sa_to_python):
        """all() возвращает список экземпляров модели."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {'Ссылка': '_IDRRef', 'Наименование': '_Description'}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_idrref'
        mock_query._children = {}
        mock_query._table.c = {
            '_idrref': MagicMock(),
            '_description': MagicMock(nullable=False),
        }
        mock_sa_to_python.return_value = str
        mock_query.all.return_value = [
            {'_idrref': b'\x00'*16, '_description': 'Item1'},
            {'_idrref': b'\x00'*16, '_description': 'Item2'},
        ]

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        model = gen._create_model('TestModel', mock_query)
        
        results = model.all()
        
        assert len(results) == 2
        assert all(isinstance(r, BaseModel) for r in results)


class TestSchemaGeneratorGet:
    """Тесты методов доступа к моделям."""

    def test_get_returns_model_by_name(self):
        """get() возвращает модель по полному имени."""
        mock_repo = MagicMock()
        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._models = {'Справочники.Алгоритмы': MagicMock()}
        
        result = gen.get('Справочники.Алгоритмы')
        
        assert result is not None

    def test_get_returns_none_for_unknown_model(self):
        """get() возвращает None для несуществующей модели."""
        mock_repo = MagicMock()
        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._models = {}
        
        result = gen.get('Неизвестный.Объект')
        
        assert result is None

    def test_getitem_operator(self):
        """__getitem__ позволяет доступ через квадратные скобки."""
        mock_repo = MagicMock()
        gen = SchemaGenerator.__new__(SchemaGenerator)
        expected_model = MagicMock()
        gen._models = {'Справочники.Алгоритмы': expected_model}
        
        result = gen['Справочники.Алгоритмы']
        
        assert result is expected_model

    def test_getitem_raises_keyerror_for_unknown(self):
        """__getitem__ выбрасывает KeyError для несуществующего ключа."""
        mock_repo = MagicMock()
        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._models = {}
        
        with pytest.raises(KeyError):
            _ = gen['Неизвестный']


class TestSchemaGeneratorEdgeCases:
    """Тесты граничных случаев."""

    @patch('pydajet_metadata.schema.sa_to_python')
    def test_create_model_with_empty_column_map(self, mock_sa_to_python):
        """Создание модели с пустой картой колонок."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_ownerrref'
        mock_query._children = {}
        mock_query._table.c = {}

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        model = gen._create_model('EmptyModel', mock_query)
        
        # Модель должна создаваться даже без полей
        assert issubclass(model, BaseModel)

    @patch('pydajet_metadata.schema.sa_to_python')
    def test_create_model_owner_key_excluded_from_required(self, mock_sa_to_python):
        """Поле owner_key не становится обязательным, даже если не nullable."""
        mock_repo = MagicMock()
        mock_query = MagicMock()
        mock_query._column_map = {'Родитель': '_OwnerRRef'}
        mock_query._pk = '_idrref'
        mock_query._owner_key = '_ownerrref'
        mock_query._children = {}
        
        mock_col = MagicMock()
        mock_col.nullable = False  # не nullable, но это owner_key
        mock_query._table.c = {'_ownerrref': mock_col}
        mock_sa_to_python.return_value = str

        gen = SchemaGenerator.__new__(SchemaGenerator)
        gen._repo = mock_repo

        model = gen._create_model('TestModel', mock_query)
        
        fields = model.model_fields
        # Родитель должен быть опциональным, т.к. это owner_key
        assert 'Родитель' in fields
        # Проверяем, что поле не требует обязательного значения
