"""
schema.py — Генератор Pydantic-моделей из метаданных 1С.
"""
from typing import Optional

from pydajet_metadata._types import sa_to_python
from pydajet_metadata._uuid import format_uuid , from_1c , to_1c
from pydajet_metadata.repository import Repository
from pydantic import BaseModel , Field , create_model


class SchemaGenerator :
	"""Генератор Pydantic-моделей."""

	def __init__ ( self , repo: Repository ) :
		self._repo = repo
		self._models: dict [ str , type [ BaseModel ] ] = { }
		self._generate ( )

	def _generate ( self ) :
		for type_name in self._repo.types ( ) :
			for obj_name in self._repo.objects ( type_name ) :
				query = self._repo.query ( type_name , obj_name )
				model = self._create_model ( obj_name , query )
				self._models [ f"{type_name}.{obj_name}" ] = model

	def _create_model ( self , name: str , query: 'Query' ) -> type [ BaseModel ] :
		fields = { }

		for human , db_name in query._column_map.items ( ) :
			col = query._table.c [ db_name.lower ( ) ]
			py_type = sa_to_python ( col.type )

			if db_name.lower ( ) == query._pk :
				fields [ human ] = (Optional [ str ] , Field ( default = None ))
			elif not col.nullable and db_name.lower ( ) != query._owner_key :
				fields [ human ] = (py_type , Field ( ... ))
			else :
				fields [ human ] = (Optional [ py_type ] , Field ( default = None ))

		# Табличные части
		for child_name , child_query in getattr ( query , '_children' , { } ).items ( ) :
			child_model = self._create_model ( child_name , child_query )
			fields [ child_name ] = (Optional [ list [ child_model ] ] , Field ( default_factory = list ))

		model = create_model ( name , **fields , __module__ = __name__ )
		model._query = query

		# Методы
		@classmethod
		def from_db ( cls , record_id: str ) :
			row = query.where ( query._table.c [ query._pk ] == to_1c ( record_id ) ).first ( )
			if row :
				for child_name , child_query in getattr ( query , '_children' , { } ).items ( ) :
					child_rows = child_query.where (
						child_query._table.c [ child_query._owner_key ] == to_1c ( record_id )
					).all ( )
					row [ child_name ] = [ child_model ( **r ) for r in child_rows ]
				return cls ( **row )
			return None

		def save ( self ) :
			data = self.model_dump ( exclude_none = True )
			parts = { }
			for child_name in getattr ( query , '_children' , { } ) :
				if child_name in data and data [ child_name ] :
					parts [ child_name ] = [
						item.model_dump ( exclude_none = True ) if isinstance ( item , BaseModel ) else item
						for item in data [ child_name ]
					]
				data.pop ( child_name , None )

			pk = data.get ( 'Ссылка' ) or data.get ( list ( query._column_map.keys ( ) ) [ 0 ] )

			if pk and query.count ( ) :
				query.update ( pk , data )
			else :
				pk = query.insert ( data )
				self.Ссылка = pk

			if parts :
				for child_name , rows in parts.items ( ) :
					child_query = getattr ( query , '_children' , { } ) [ child_name ]
					for row in rows :
						row [ child_query._owner_key ] = pk
						child_query.insert ( row )

			return self

		def delete ( self ) :
			pk = self.Ссылка
			if pk :
				for child_query in getattr ( query , '_children' , { } ).values ( ) :
					child_query.delete ( pk )
				query.delete ( pk )
			return self

		model.from_db = classmethod ( from_db )
		model.save = save
		model.delete = delete

		@classmethod
		def all ( cls ) :
			return [ cls ( **r ) for r in query.all ( ) ]

		model.all = classmethod ( all )

		return model

	def get ( self , name: str ) -> type [ BaseModel ] :
		return self._models.get ( name )

	def __getitem__ ( self , name: str ) -> type [ BaseModel ] :
		return self._models [ name ]
