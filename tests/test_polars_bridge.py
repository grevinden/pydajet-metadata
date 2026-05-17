"""Тесты PolarsBridge."""
import pytest
from unittest.mock import MagicMock , patch
import polars as pl
from datetime import datetime

from pydajet_metadata.bridge import PolarsBridge


class TestPolarsBridge :
	"""Тесты Polars-интеграции."""

	@pytest.fixture
	def mock_repo ( self ) :
		repo = MagicMock ( )
		return repo

	@pytest.fixture
	def bridge ( self , mock_repo ) :
		return PolarsBridge ( mock_repo )

	def test_read_empty(self, bridge, mock_repo):
		mock_query = MagicMock()
		mock_query.all.return_value = []
		mock_query._column_map = {'Наименование': '_Description', 'Код': '_Code'}
		# Добавить мок-колонки
		mock_query._table = MagicMock()
		mock_query._table.c = {
			'_description': MagicMock(),
			'_code': MagicMock(),
		}
		mock_query._table.c['_description'].__str__ = lambda: 'VARCHAR(150)'
		mock_query._table.c['_code'].__str__ = lambda: 'VARCHAR(50)'
		mock_repo.query.return_value = mock_query

		df = bridge.read('Справочники', 'ирАлгоритмы')
		assert df.height == 0

	def test_write ( self , bridge , mock_repo ) :
		mock_query = MagicMock ( )
		mock_query.all.return_value = [ ]
		mock_query._children = { }
		mock_repo.query.return_value = mock_query

		df = pl.DataFrame ( [
			{ 'Наименование' : 'Тест 1' , 'Код' : '001' } ,
			{ 'Наименование' : 'Тест 2' , 'Код' : '002' } ,
		] )

		count = bridge.write ( df , 'Справочники' , 'ирАлгоритмы' )
		assert count == 2
		assert mock_query.insert.call_count == 2
