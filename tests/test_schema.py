"""Тесты SchemaGenerator."""
import pytest
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
