"""Тесты маппинга типов."""
import pytest
from datetime import datetime
from sqlalchemy.types import Integer , String , Boolean , DateTime , LargeBinary , Float
from pydajet_metadata._types import pg_to_sqlalchemy , sa_to_python


class TestTypeMapping :
	"""Маппинг типов PostgreSQL → SQLAlchemy → Python."""

	@pytest.mark.parametrize ( "pg_type,expected" , [
		('bytea' , LargeBinary) ,
		('integer' , Integer) ,
		('boolean' , Boolean) ,
		('timestamp without time zone' , DateTime) ,
		('timestamp' , DateTime) ,
		('character varying(150)' , String) ,
		('mvarchar' , String) ,
		('varchar(50)' , String) ,
		('text' , String) ,
		('numeric(10,2)' , Float) ,
		('bigint' , Integer) ,
		('double precision' , Float) ,
		('real' , Float) ,
	] )
	def test_pg_to_sqlalchemy ( self , pg_type , expected ) :
		assert pg_to_sqlalchemy ( pg_type ) == expected

	def test_pg_to_sqlalchemy_unknown ( self ) :
		assert pg_to_sqlalchemy ( 'some_unknown_type' ) == String

	@pytest.mark.parametrize ( "sa_type,expected" , [
		('VARCHAR(150)' , str) ,
		('mvarchar' , str) ,
		('TEXT' , str) ,
		('INTEGER' , int) ,
		('BOOLEAN' , bool) ,
		('TIMESTAMP' , datetime) ,
		('FLOAT' , float) ,
		('BYTEA' , bytes) ,
	] )
	def test_sa_to_python ( self , sa_type , expected ) :
		mock_col = type ( 'MockCol' , () ,
		                  { 'type' : type ( 'MockType' , () , { '__str__' : lambda s : sa_type } ) ( ) } ) ( )
		assert sa_to_python ( mock_col.type ) == expected
