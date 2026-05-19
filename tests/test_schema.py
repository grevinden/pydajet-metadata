"""Тесты SchemaGenerator."""
import pytest
from sqlalchemy.types import String
from unittest.mock import MagicMock , patch
from pydajet_metadata.schema import SchemaGenerator


class TestSchemaGenerator :
	"""Тесты генератора Pydantic-моделей."""

	@pytest.fixture
	def mock_repo ( self ) :
		repo = MagicMock ( )
		repo.types.return_value = [ 'Справочники' ]
		repo.objects.return_value = [ 'ирАлгоритмы' ]
		return repo

	def test_model_creation ( self , mock_repo ) :
		mock_query = MagicMock ( )
		mock_query._column_map = {
			'Ссылка'       : '_IDRRef' ,
			'Наименование' : '_Description' ,
			'Код'          : '_Code' ,
		}
		mock_query._pk = '_idrref'
		mock_query._owner_key = '_idrref'
		mock_query._children = { }
		mock_repo.query.return_value = mock_query

		gen = SchemaGenerator ( mock_repo )
		model = gen.get ( 'Справочники.ирАлгоритмы' )

		assert model is not None
		assert hasattr ( model , 'from_db' )
		assert hasattr ( model , 'save' )
		assert hasattr ( model , 'delete' )
		assert hasattr ( model , 'all' )

	def test_model_all_and_from_db_with_children(self, mock_repo):
		child_query = MagicMock()
		child_query._column_map = {'Ссылка': '_IDRRef'}
		child_query._pk = '_idrref'
		child_query._owner_key = '_parent_rref'
		child_query._children = {}
		child_query._table = MagicMock()
		child_query._table.c = {
			'_parent_rref': MagicMock(),
			'_idrref': MagicMock(),
		}
		child_query._table.c['_parent_rref'].nullable = True
		child_query._table.c['_parent_rref'].type = String()
		child_query._table.c['_idrref'].nullable = False
		child_query._table.c['_idrref'].type = String()
		child_query.where.return_value.all.return_value = [{'Ссылка': '9c280050-b666-dffa-11f1-4e880e761abe'}]

		mock_query = MagicMock()
		mock_query._column_map = {
			'Ссылка': '_IDRRef',
			'Наименование': '_Description',
		}
		mock_query._pk = '_idrref'
		mock_query._owner_key = '_idrref'
		mock_query._children = {'ТабличнаяЧасть': child_query}
		mock_query._table = MagicMock()
		mock_query._table.c = {'_idrref': MagicMock(), '_description': MagicMock()}
		mock_query._table.c['_idrref'].nullable = False
		mock_query._table.c['_description'].nullable = True
		mock_query._table.c['_idrref'].type = String()
		mock_query._table.c['_description'].type = String()
		mock_query.where.return_value.first.return_value = {'Ссылка': '9c280050-b666-dffa-11f1-4e880e761abe', 'Наименование': 'Тест'}

		mock_repo.query.return_value = mock_query
		mock_repo.objects.return_value = ['ирАлгоритмы']

		gen = SchemaGenerator(mock_repo)
		model_cls = gen.get('Справочники.ирАлгоритмы')
		assert model_cls is not None
		instance = model_cls.from_db('9c280050-b666-dffa-11f1-4e880e761abe')
		assert instance is not None
		assert hasattr(instance, 'ТабличнаяЧасть')
		assert isinstance(instance.ТабличнаяЧасть, list)
