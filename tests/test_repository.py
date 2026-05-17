"""Тесты Repository."""
import pytest
from unittest.mock import MagicMock , patch
from pydajet_metadata.repository import Repository , TypeAccessor


class TestRepository :
	"""Тесты репозитория."""

	@pytest.fixture
	def mock_client ( self ) :
		client = MagicMock ( )
		client.list_types.return_value = [ 'Справочники' , 'Документы' ]
		client.list_objects.return_value = [
			{
				'name'       : 'Справочник.ирАлгоритмы' ,
				'short_name' : 'ирАлгоритмы' ,
				'table'      : '_Reference53' ,
				'properties' : [
					{ 'name' : 'Ссылка' , 'columns' : [ { 'name' : '_IDRRef' , 'type' : 'binary(16,fixed)' } ] } ,
					{ 'name' : 'Наименование' , 'columns' : [ { 'name' : '_Description' , 'type' : 'string(150)' } ] } ,
				] ,
				'children'   : [ ] ,
			} ,
			{
				'name'       : 'Справочник.ТемыУведомлений' ,
				'short_name' : 'ТемыУведомлений' ,
				'table'      : '_Reference147' ,
				'properties' : [
					{ 'name' : 'Ссылка' , 'columns' : [ { 'name' : '_IDRRef' , 'type' : 'binary(16,fixed)' } ] } ,
					{ 'name' : 'Код' , 'columns' : [ { 'name' : '_Code' , 'type' : 'string(50)' } ] } ,
				] ,
				'children'   : [ ] ,
			} ,
		]
		return client

	@pytest.fixture
	def mock_session ( self ) :
		session = MagicMock ( )
		session.reflect_table = MagicMock ( )
		session.get_pk = MagicMock ( return_value = '_idrref' )
		return session

	@patch ( 'pydajet.client.MetadataClient' )
	@patch ( 'pydajet_metadata.repository.Session' )
	def test_types ( self , mock_session_cls , mock_client_cls , mock_client , mock_session ) :
		mock_client_cls.return_value = mock_client
		mock_session_cls.return_value = mock_session

		repo = Repository ( "Host=localhost;Database=TestDB;Username=test;Password=test;" )

		assert repo.types ( ) == [ 'Документы' , 'Справочники' ]

	@patch ( 'pydajet.client.MetadataClient' )
	@patch ( 'pydajet_metadata.repository.Session' )
	def test_objects ( self , mock_session_cls , mock_client_cls , mock_client , mock_session ) :
		mock_client_cls.return_value = mock_client
		mock_session_cls.return_value = mock_session

		repo = Repository ( "Host=localhost;Database=TestDB;Username=test;Password=test;" )

		objects = repo.objects ( 'Справочники' )
		assert 'ирАлгоритмы' in objects
		assert 'ТемыУведомлений' in objects

	@patch ( 'pydajet.client.MetadataClient' )
	@patch ( 'pydajet_metadata.repository.Session' )
	def test_query ( self , mock_session_cls , mock_client_cls , mock_client , mock_session ) :
		mock_client_cls.return_value = mock_client
		mock_session_cls.return_value = mock_session

		repo = Repository ( "Host=localhost;Database=TestDB;Username=test;Password=test;" )

		q = repo.query ( 'Справочники' , 'ирАлгоритмы' )
		assert q is not None

	@patch ( 'pydajet.client.MetadataClient' )
	@patch ( 'pydajet_metadata.repository.Session' )
	def test_query_invalid_type ( self , mock_session_cls , mock_client_cls , mock_client , mock_session ) :
		mock_client_cls.return_value = mock_client
		mock_session_cls.return_value = mock_session

		repo = Repository ( "Host=localhost;Database=TestDB;Username=test;Password=test;" )

		with pytest.raises ( KeyError ) :
			repo.query ( 'НесуществующийТип' , 'Объект' )

	@patch ( 'pydajet.client.MetadataClient' )
	@patch ( 'pydajet_metadata.repository.Session' )
	def test_attr_access ( self , mock_session_cls , mock_client_cls , mock_client , mock_session ) :
		mock_client_cls.return_value = mock_client
		mock_session_cls.return_value = mock_session

		repo = Repository ( "Host=localhost;Database=TestDB;Username=test;Password=test;" )

		accessor = repo.Справочники
		assert isinstance ( accessor , TypeAccessor )
		assert accessor.list ( ) == [ 'ирАлгоритмы' , 'ТемыУведомлений' ]
