"""Тесты Session."""
import pytest
from unittest.mock import MagicMock , patch
from pydajet_metadata.session import Session


class TestSession :
	"""Тесты сессии подключения к БД."""

	def test_parse_connection_string ( self , sample_connection_string ) :
		session = Session ( sample_connection_string )
		params = session._parse_cs ( sample_connection_string )
		assert params == {
			'host'     : 'localhost' ,
			'port'     : '5433' ,
			'database' : 'testdb' ,
			'username' : 'test' ,
			'password' : 'test' ,
		}

	def test_parse_cs_case_insensitive ( self ) :
		cs = "HOST=Server;PORT=5432;DATABASE=DB;USERNAME=U;PASSWORD=P"
		result = Session._parse_cs ( cs )
		assert result == {
			'host'     : 'server' ,
			'port'     : '5432' ,
			'database' : 'db' ,
			'username' : 'u' ,
			'password' : 'p' ,
		}

	def test_parse_cs_empty ( self ) :
		assert Session._parse_cs ( "" ) == { }

	def test_parse_cs_extra_semicolons ( self ) :
		cs = "Host=localhost;;Port=5432;"
		result = Session._parse_cs ( cs )
		assert result == { 'host' : 'localhost' , 'port' : '5432' }

	@patch ( 'pydajet_metadata.session.create_engine' )
	@patch ( 'pydajet_metadata.session.inspect' )
	def test_init_creates_engine ( self , mock_inspect , mock_engine , sample_connection_string ) :
		session = Session ( sample_connection_string )
		mock_engine.assert_called_once ( )
		assert session._engine is not None

	@patch ( 'pydajet_metadata.session.create_engine' )
	@patch ( 'pydajet_metadata.session.inspect' )
	def test_close_disposes_engine ( self , mock_inspect , mock_engine , sample_connection_string ) :
		session = Session ( sample_connection_string )
		session._engine.dispose = MagicMock ( )
		session.close ( )
		session._engine.dispose.assert_called_once ( )
