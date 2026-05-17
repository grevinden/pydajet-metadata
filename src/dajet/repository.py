"""
repository.py — Репозиторий объектов 1С.
Связывает метаданные с Query, предоставляет единый интерфейс.
"""

from pydajet_metadata.query import Query
from pydajet_metadata.session import Session

from pydajet_metadata.client import MetadataClient


class Repository :
	"""
	Репозиторий для работы с объектами 1С.

	Пример:
			repo = Repository("Host=...;Database=...;...")

			# Список типов
			repo.types()  # ['Справочники', 'Документы', ...]

			# Список объектов типа
			repo.objects('Справочники')  # ['ирАлгоритмы', ...]

			# Query для объекта
			q = repo.query('Справочники', 'ирАлгоритмы')
			q.all()
			q.insert({'Наименование': 'Тест'})
	"""

	def __init__ ( self , connection_string: str , data_source: str = "postgresql" ) :
		self._client = MetadataClient ( connection_string , data_source )
		self._session = Session ( connection_string )
		self._queries: dict [ str , dict [ str , Query ] ] = { }
		self._build ( )

	def _build ( self ) :
		"""Строит все Query из метаданных."""
		for type_name in self._client.list_types ( ) :
			self._queries [ type_name ] = { }
			for obj in self._client.list_objects ( type_name ) :
				# Основная таблица
				column_map = { }
				pk = '_idrref'
				for prop in obj [ 'properties' ] :
					if prop [ 'columns' ] :
						db_name = prop [ 'columns' ] [ 0 ] [ 'name' ]
						column_map [ prop [ 'name' ] ] = db_name
						if db_name.lower ( ) in ('_idrref' , '_recordkey') :
							pk = db_name.lower ( )

				table_name = obj [ 'table' ]
				pk = self._session.get_pk ( table_name ) or pk

				query = Query ( self._session , table_name , column_map , pk )

				# Табличные части
				for child in obj [ 'children' ] :
					child_map = { }
					child_pk = '_idrref'
					child_owner = '_idrref'

					for prop in child [ 'properties' ] :
						if prop [ 'columns' ] :
							db_name = prop [ 'columns' ] [ 0 ] [ 'name' ]
							child_map [ prop [ 'name' ] ] = db_name
							if db_name.lower ( ) in ('_idrref' , '_recordkey') :
								child_pk = db_name.lower ( )
							if db_name.lower ( ).endswith ( '_rref' ) and db_name.lower ( ) != child_pk :
								child_owner = db_name.lower ( )

					child_table = child [ 'table' ]
					child_pk = self._session.get_pk ( child_table ) or child_pk

					child_query = Query ( self._session , child_table , child_map , child_pk , child_owner )
					query._children [ child [ 'name' ] ] = child_query
					setattr ( query , child [ 'name' ] , child_query )

				self._queries [ type_name ] [ obj [ 'short_name' ] ] = query

	def types ( self ) -> list [ str ] :
		"""Список всех типов объектов."""
		return sorted ( self._queries.keys ( ) )

	def objects ( self , type_name: str ) -> list [ str ] :
		"""Список объектов указанного типа."""
		if type_name not in self._queries :
			return [ ]
		return sorted ( self._queries [ type_name ].keys ( ) )

	def query ( self , type_name: str , object_name: str ) -> Query :
		"""Возвращает Query для объекта."""
		if type_name not in self._queries :
			raise KeyError ( f"Type '{type_name}' not found" )
		if object_name not in self._queries [ type_name ] :
			raise KeyError ( f"Object '{object_name}' not found in '{type_name}'" )
		return self._queries [ type_name ] [ object_name ]

	def __getattr__ ( self , name: str ) :
		"""Доступ к типу: repo.Справочники"""
		if name in self._queries :
			return TypeAccessor ( self , name )
		raise AttributeError ( f"Type '{name}' not found" )

	@property
	def session ( self ) -> Session :
		return self._session

	def close ( self ) :
		self._session.close ( )


class TypeAccessor :
	"""Доступ к объектам типа: repo.Справочники['ирАлгоритмы']"""

	def __init__ ( self , repo: Repository , type_name: str ) :
		self._repo = repo
		self._type = type_name

	def __getitem__ ( self , name: str ) -> Query :
		return self._repo.query ( self._type , name )

	def __getattr__ ( self , name: str ) -> Query :
		return self._repo.query ( self._type , name )

	def list ( self ) -> list [ str ] :
		return self._repo.objects ( self._type )

	def __iter__ ( self ) :
		return iter ( self.list ( ) )
