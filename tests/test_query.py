"""Тесты Query builder."""
import pytest
from unittest.mock import MagicMock , patch , call
from datetime import datetime
from sqlalchemy import Table , Column , MetaData
from sqlalchemy.types import Integer , String , Boolean , DateTime , LargeBinary

from pydajet._uuid import to_1c , from_1c
from pydajet_metadata.query import Query


class TestQuery :
	"""Тесты построителя запросов."""

	@pytest.fixture
	def mock_session ( self ) :
		session = MagicMock ( )
		session.engine = MagicMock ( )
		session.reflect_table = MagicMock ( )
		return session

	@pytest.fixture
	def mock_table ( self ) :
		metadata = MetaData ( )
		return Table ( '_reference53' , metadata ,
		               Column ( '_idrref' , LargeBinary ) ,
		               Column ( '_version' , Integer ) ,
		               Column ( '_marked' , Boolean ) ,
		               Column ( '_description' , String ) ,
		               Column ( '_code' , String ) ,
		               Column ( '_fld56' , String ) ,
		               Column ( '_fld57' , DateTime ) ,
		               Column ( '_fld58' , String ) ,
		               Column ( '_predefinedid' , LargeBinary ) ,
		               )

	@pytest.fixture
	def query ( self , mock_session , mock_table , sample_column_map ) :
		mock_session.reflect_table.return_value = mock_table
		return Query ( mock_session , '_reference53' , sample_column_map )

	def test_column_access_by_human_name ( self , query ) :
		col = query.Наименование
		assert col.name == '_description'

	def test_column_access_invalid ( self , query ) :
		with pytest.raises ( AttributeError ) :
			_ = query.НесуществующаяКолонка

	def test_row_to_dict ( self , query , sample_row_data ) :
		"""Проверяет конвертацию строки БД в словарь с человеческими именами."""
		mock_row = MagicMock ( )

		def mock_getattr ( instance , name ) :
			return sample_row_data.get ( name )

		type ( mock_row ).__getattr__ = mock_getattr
		mock_row._mapping = sample_row_data

		with patch.object ( query , '_row_to_dict' , wraps = query._row_to_dict ) as wrapped :
			result = query._row_to_dict ( mock_row )

		assert result [ 'Наименование' ] == 'Тестовый алгоритм'
		assert result [ 'Код' ] == '001'
		assert result [ 'ТекстАлгоритма' ] == 'Сообщить("Привет");'
		assert '9c280050' in result [ 'Ссылка' ]  # UUID с дефисами

	def test_human_to_db ( self , query ) :
		data = {
			'Наименование'   : 'Тест' ,
			'Код'            : '001' ,
			'ТекстАлгоритма' : 'Сообщить("Привет");' ,
		}
		result = query._human_to_db ( data )
		assert result [ '_description' ] == 'Тест'
		assert result [ '_code' ] == '001'
		assert result [ '_fld56' ] == 'Сообщить("Привет");'

	def test_default_values ( self , query ) :
		for col in query._table.columns :
			default = query._default ( col )
			if col.name == '_version' :
				assert default == 0
			elif col.name == '_marked' :
				assert default == False

	def test_fill_defaults ( self , query ) :
		db = { '_description' : 'Тест' }
		query._fill_defaults ( db )
		assert db [ '_version' ] == 0
		assert db [ '_marked' ] == False

	@patch ( 'pydajet_metadata.query.insert' )
	def test_insert ( self , mock_insert , query ) :
		mock_insert.return_value.values.return_value = MagicMock ( )
		query._session.engine.begin = MagicMock ( )
		query._session.engine.begin.return_value.__enter__ = MagicMock ( )

		result = query.insert ( { 'Наименование' : 'Новый' } )
		assert result is not None
		assert len ( result ) == 36  # UUID с дефисами
