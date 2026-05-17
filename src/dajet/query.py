"""
query.py — Query builder для таблиц 1С.
"""
from datetime import datetime
from typing import Optional , Any

from pydajet_metadata._uuid import generate , to_1c , from_1c , format_uuid
from pydajet_metadata.session import Session
from sqlalchemy import select , func , insert , update , delete
from sqlalchemy.types import String , Boolean , Integer , Float , LargeBinary , DateTime


class Query :
	"""Построитель запросов к одной таблице 1С."""

	def __init__ (
			self , session: Session , table_name: str , column_map: dict [ str , str ] , pk: str = '_idrref' ,
			owner_key: str = '_idrref' ) :
		self._session = session
		self._table = session.reflect_table ( table_name )
		self._column_map = column_map
		self._reverse_map = { v.lower ( ) : k for k , v in column_map.items ( ) }
		self._pk = pk.lower ( )
		self._owner_key = owner_key.lower ( )
		self._where = [ ]

	def __getattr__ ( self , name: str ) :
		if name in self._column_map :
			db = self._column_map [ name ].lower ( )
			if db in self._table.c :
				return self._table.c [ db ]
		raise AttributeError ( f"Column '{name}' not found" )

	def where ( self , *conditions ) :
		self._where = list ( conditions )
		return self

	# ─── Read ─────────────────────────────────────────

	def all ( self ) -> list [ dict [ str , Any ] ] :
		stmt = select ( self._table )
		for c in self._where :
			stmt = stmt.where ( c )
		with self._session.engine.connect ( ) as conn :
			return [ self._row_to_dict ( r ) for r in conn.execute ( stmt ).all ( ) ]

	def first ( self ) -> Optional [ dict [ str , Any ] ] :
		stmt = select ( self._table ).limit ( 1 )
		for c in self._where :
			stmt = stmt.where ( c )
		with self._session.engine.connect ( ) as conn :
			row = conn.execute ( stmt ).first ( )
			return self._row_to_dict ( row ) if row else None

	def count ( self ) -> int :
		stmt = select ( func.count ( ) ).select_from ( self._table )
		for c in self._where :
			stmt = stmt.where ( c )
		with self._session.engine.connect ( ) as conn :
			return conn.execute ( stmt ).scalar ( )

	# ─── Write ────────────────────────────────────────

	def insert ( self , data: dict [ str , Any ] , extra: dict [ str , Any ] = None ) -> str :
		"""Вставляет запись. Возвращает UUID."""
		new_uuid = generate ( )
		db = self._human_to_db ( data )
		db [ self._pk ] = to_1c ( new_uuid )

		if extra :
			for k , v in extra.items ( ) :
				if isinstance ( v , str ) and len ( v.replace ( '-' , '' ) ) == 32 :
					extra [ k ] = to_1c ( v )
			db.update ( extra )

		self._fill_defaults ( db )

		stmt = insert ( self._table ).values ( **db )
		with self._session.engine.begin ( ) as conn :
			conn.execute ( stmt )

		return format_uuid ( new_uuid )

	def update ( self , record_id: str , data: dict [ str , Any ] ) -> bool :
		db = self._human_to_db ( data )
		stmt = update ( self._table ).where ( self._table.c [ self._pk ] == to_1c ( record_id ) ).values ( **db )
		with self._session.engine.begin ( ) as conn :
			return conn.execute ( stmt ).rowcount > 0

	def delete ( self , record_id: str ) -> bool :
		stmt = delete ( self._table ).where ( self._table.c [ self._pk ] == to_1c ( record_id ) )
		with self._session.engine.begin ( ) as conn :
			return conn.execute ( stmt ).rowcount > 0

	# ─── Internal ─────────────────────────────────────

	def _row_to_dict ( self , row ) -> dict [ str , Any ] :
		d = { }
		for col in self._table.columns :
			human = self._reverse_map.get ( col.name.lower ( ) , col.name )
			val = getattr ( row , col.name )
			if isinstance ( val , bytes ) and len ( val ) == 16 :
				val = format_uuid ( from_1c ( val ) )
			elif isinstance ( val , bytes ) :
				val = val.hex ( )
			d [ human ] = val
		return d

	def _human_to_db ( self , data: dict [ str , Any ] ) -> dict [ str , Any ] :
		db = { }
		for human , value in data.items ( ) :
			if human in self._column_map :
				db_name = self._column_map [ human ].lower ( )
				if isinstance ( value , str ) and self._is_binary ( db_name ) :
					try :
						value = to_1c ( value )
					except (ValueError , AttributeError) :
						pass
				db [ db_name ] = value
			else :
				db [ human.lower ( ) ] = value
		return db

	def _fill_defaults ( self , db: dict ) :
		for col in self._table.columns :
			name = col.name.lower ( )
			if name not in db :
				d = self._default ( col )
				if d is not None :
					db [ name ] = d

	def _default ( self , col ) -> Any :
		name = col.name.lower ( )
		if name == '_version' : return 0
		if name == '_marked' : return False
		if name == '_posted' : return True
		if name == '_date_time' : return datetime.now ( )
		if name == '_number' : return ''
		if name == '_keyfield' : return to_1c ( generate ( ) )
		if name.endswith ( '_rref' ) : return b'\x00' * 16
		if name.endswith ( '_rtref' ) : return b'\x00' * 4
		if name.endswith ( '_type' ) : return b'\x00' * 1
		if isinstance ( col.type , String ) : return ''
		if isinstance ( col.type , Boolean ) : return False
		if isinstance ( col.type , (Integer , Float) ) : return 0
		if isinstance ( col.type , LargeBinary ) : return b'\x00' * 16
		if isinstance ( col.type , DateTime ) : return datetime.now ( )
		return None

	def _is_binary ( self , col_name: str ) -> bool :
		return col_name in self._table.c and isinstance ( self._table.c [ col_name ].type , LargeBinary )
