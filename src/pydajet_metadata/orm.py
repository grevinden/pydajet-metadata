"""
reader.py — ORM-читалка для 1С с человеческими названиями колонок.
Поддерживает чтение, добавление, изменение и удаление записей,
включая табличные части. Корректно конвертирует UUID между форматами 1С и PostgreSQL.
"""
import uuid as _uuid
import warnings
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Optional , Any

from sqlalchemy import exc as sa_exc

warnings.filterwarnings ( 'ignore' , category = sa_exc.SAWarning )

from sqlalchemy import create_engine , inspect , Table , Column , MetaData , select , func , insert , update , delete
from sqlalchemy.types import Integer , String , Boolean , DateTime , LargeBinary , Float

from pydajet_metadata.client import MetadataClient

# Маппинг типов PostgreSQL → SQLAlchemy
TYPE_MAP = {
	'bytea'             : LargeBinary ,
	'integer'           : Integer ,
	'boolean'           : Boolean ,
	'timestamp'         : DateTime ,
	'character varying' : String ,
	'mvarchar'          : String ,
	'varchar'           : String ,
	'text'              : String ,
	'numeric'           : Float ,
	'bigint'            : Integer ,
	'smallint'          : Integer ,
	'double precision'  : Float ,
	'real'              : Float ,
}


# ─── UUID конвертация 1С ↔ PostgreSQL ─────────────────

def uuid_1c_to_db ( uuid_bytes: bytes ) -> bytes :
	"""
	Конвертирует UUID из формата 1С в формат PostgreSQL.
	1С хранит первые 8 байт в обратном порядке: [3,2,1,0,5,4,7,6,8..15]
	"""
	if len ( uuid_bytes ) != 16 :
		return uuid_bytes
	d = list ( uuid_bytes )
	return bytes ( [ d [ 3 ] , d [ 2 ] , d [ 1 ] , d [ 0 ] , d [ 5 ] , d [ 4 ] , d [ 7 ] , d [ 6 ] , *d [ 8 :16 ] ] )


def uuid_db_to_1c ( uuid_bytes: bytes ) -> bytes :
	"""
	Конвертирует UUID из формата PostgreSQL в формат 1С.
	Операция симметрична uuid_1c_to_db.
	"""
	if len ( uuid_bytes ) != 16 :
		return uuid_bytes
	d = list ( uuid_bytes )
	return bytes ( [ d [ 3 ] , d [ 2 ] , d [ 1 ] , d [ 0 ] , d [ 5 ] , d [ 4 ] , d [ 7 ] , d [ 6 ] , *d [ 8 :16 ] ] )


def uuid_1c_to_hex ( uuid_bytes: bytes ) -> str :
	"""Конвертирует 1С UUID в hex-строку (стандартный вид)."""
	return uuid_db_to_1c ( uuid_bytes ).hex ( )


def hex_to_uuid_1c ( hex_str: str ) -> bytes :
	"""Конвертирует hex-строку в 1С UUID (перевёрнутый)."""
	return uuid_1c_to_db ( bytes.fromhex ( hex_str ) )


# ─── Декоратор validate_call (если pydantic не установлен) ───

try :
	from pydantic import validate_call
except ImportError :
	# Простая заглушка без проверки типов
	def validate_call ( func ) :
		@wraps ( func )
		def wrapper ( *args , **kwargs ) :
			return func ( *args , **kwargs )

		return wrapper


class TableQuery :
	"""Обёртка над SQLAlchemy Table с человеческими названиями колонок.
	Поддерживает: all(), first(), count(), where(), Добавить(), Изменить(), Удалить(),
								ТабличныеЧасти, ДобавитьСЧастями().
	Все UUID автоматически конвертируются между форматами 1С и PostgreSQL.
	"""

	def __init__ (
			self ,
			table: Table ,
			engine ,
			column_map: dict [ str , str ] ,
			primary_key: str = '_idrref' ,
			owner_key: str = '_idrref' ,
			children: Optional [ dict [ str , 'TableQuery' ] ] = None ,
	) :
		"""
		Args:
				table: SQLAlchemy Table
				engine: SQLAlchemy engine
				column_map: словарь {человеческое_имя: имя_колонки_в_бд}
				primary_key: имя первичного ключа в БД
				owner_key: имя колонки-владельца для табличных частей
				children: словарь {имя_табличной_части: TableQuery}
		"""
		self.table = table
		self.engine = engine
		self._column_map = column_map
		self._reverse_map = { v.lower ( ) : k for k , v in column_map.items ( ) }
		self._primary_key = primary_key.lower ( )
		self._owner_key = owner_key.lower ( )
		self._where: list = [ ]

		# Табличные части
		self._children = children or { }
		for name , child_query in self._children.items ( ) :
			setattr ( self , name , child_query )

	def __getattr__ ( self , name: str ) :
		"""Доступ к колонкам по человеческому имени: query.Наименование"""
		if name in self._column_map :
			db_name = self._column_map [ name ].lower ( )
			if db_name in self.table.c :
				return self.table.c [ db_name ]
		raise AttributeError (
			f"Column '{name}' not found. Available: {list ( self._column_map.keys ( ) )}" ,
		)

	def where ( self , *conditions ) :
		"""Добавляет условие WHERE."""
		self._where = conditions
		return self

	# ─── Чтение ─────────────────────────────────────────

	@validate_call
	def all ( self ) -> list [ dict [ str , Any ] ] :
		"""Все строки с человеческими именами колонок."""
		stmt = select ( self.table )
		for cond in self._where :
			stmt = stmt.where ( cond )
		with self.engine.connect ( ) as conn :
			rows = conn.execute ( stmt ).all ( )
		return [ self._row_to_dict ( r ) for r in rows ]

	@validate_call
	def first ( self ) -> Optional [ dict [ str , Any ] ] :
		"""Первая строка."""
		stmt = select ( self.table ).limit ( 1 )
		for cond in self._where :
			stmt = stmt.where ( cond )
		with self.engine.connect ( ) as conn :
			row = conn.execute ( stmt ).first ( )
		return self._row_to_dict ( row ) if row else None

	@validate_call
	def count ( self ) -> int :
		"""Количество строк."""
		stmt = select ( func.count ( ) ).select_from ( self.table )
		for cond in self._where :
			stmt = stmt.where ( cond )
		with self.engine.connect ( ) as conn :
			return conn.execute ( stmt ).scalar ( )

	# ─── Добавление ─────────────────────────────────────

	@validate_call
	def Добавить ( self , data: dict [ str , Any ] , extra_db_data: Optional [ dict [ str , Any ] ] = None ) -> str :
		new_id = uuid.uuid4 ( ).bytes
		new_id_1c = uuid_1c_to_db ( new_id )

		db_data = self._human_to_db ( data )
		db_data [ self._primary_key ] = new_id_1c

		if extra_db_data :
			for key , value in extra_db_data.items ( ) :
				if isinstance ( value , str ) and len ( value ) == 32 :
					extra_db_data [ key ] = bytes.fromhex ( value )
			db_data.update ( extra_db_data )

		for col in self.table.columns :
			col_name = col.name.lower ( )
			if col_name not in db_data :
				default = self._default_for_column ( col )
				if default is not None :
					db_data [ col_name ] = default

		stmt = insert ( self.table ).values ( **db_data )
		with self.engine.begin ( ) as conn :
			conn.execute ( stmt )

		return new_id.hex ( )

	def _default_for_column ( self , col ) -> Any :
		"""Возвращает значение по умолчанию для колонки."""
		col_name = col.name.lower ( )

		if col_name == '_version' :
			return 0
		elif col_name == '_marked' :
			return False
		elif col_name == '_posted' :
			return True
		elif col_name == '_date_time' :
			return datetime.now ( )
		elif col_name == '_number' :
			return ''
		elif col_name == '_keyfield' :
			return uuid_1c_to_db ( uuid.uuid4 ( ).bytes )  # Уникальный ключ для табличной части
		elif col_name.endswith ( '_rref' ) :
			return b'\x00' * 16
		elif col_name.endswith ( '_rtref' ) :
			return b'\x00' * 4
		elif col_name.endswith ( '_type' ) :
			return b'\x00' * 1
		elif isinstance ( col.type , String ) :
			return ''
		elif isinstance ( col.type , Boolean ) :
			return False
		elif isinstance ( col.type , (Integer , Float) ) :
			return 0
		elif isinstance ( col.type , LargeBinary ) :
			return b'\x00' * 16
		elif isinstance ( col.type , DateTime ) :
			return datetime.now ( )

		return None

	# ─── Изменение ──────────────────────────────────────

	@validate_call
	def Изменить ( self , record_id: str , data: dict [ str , Any ] ) -> bool :
		"""
		Изменяет запись по первичному ключу.

		Args:
				record_id: hex-строка _idrref (стандартный формат)
				data: словарь {человеческое_имя: новое_значение}
		"""
		pk_bytes_1c = hex_to_uuid_1c ( record_id )
		db_data = self._human_to_db ( data )

		stmt = update ( self.table ).where (
			self.table.c [ self._primary_key ] == pk_bytes_1c ,
		).values ( **db_data )

		with self.engine.begin ( ) as conn :
			result = conn.execute ( stmt )
			return result.rowcount > 0

	# ─── Удаление ───────────────────────────────────────

	@validate_call
	def Удалить ( self , record_id: str ) -> bool :
		"""
		Удаляет запись по первичному ключу.

		Args:
				record_id: hex-строка _idrref (стандартный формат)
		"""
		pk_bytes_1c = hex_to_uuid_1c ( record_id )

		stmt = delete ( self.table ).where (
			self.table.c [ self._primary_key ] == pk_bytes_1c ,
		)

		with self.engine.begin ( ) as conn :
			result = conn.execute ( stmt )
			return result.rowcount > 0

	# ─── Вспомогательные методы ─────────────────────────

	import uuid as _uuid

	def _row_to_dict ( self , row ) -> dict [ str , Any ] :
		"""Преобразует строку в словарь с человеческими именами. UUID в стандартном формате."""
		d = { }
		for col in self.table.columns :
			col_name = self._reverse_map.get ( col.name.lower ( ) , col.name )
			val = getattr ( row , col.name )
			if isinstance ( val , bytes ) and len ( val ) == 16 :
				# Конвертируем 1С → стандартный UUID с дефисами
				val = str ( uuid.UUID ( bytes = uuid_db_to_1c ( val ) ) )
			elif isinstance ( val , bytes ) :
				val = val.hex ( )
			d [ col_name ] = val
		return d

	def _human_to_db ( self , data: dict [ str , Any ] ) -> dict [ str , Any ] :
		"""Преобразует словарь {человеческое_имя: значение} → {имя_бд: значение}."""
		db_data = { }
		for human_name , value in data.items ( ) :
			if human_name in self._column_map :
				db_name = self._column_map [ human_name ].lower ( )
				# Если значение — UUID-строка (с дефисами или без), а колонка — бинарная
				if isinstance ( value , str ) and self._is_binary_column ( db_name ) :
					try :
						# Убираем дефисы, парсим UUID, конвертируем в 1С
						clean = value.replace ( '-' , '' )
						if len ( clean ) == 32 :
							std_uuid = _uuid.UUID ( clean )
							value = uuid_1c_to_db ( std_uuid.bytes )
					except (ValueError , AttributeError) :
						pass
				db_data [ db_name ] = value
			else :
				db_data [ human_name.lower ( ) ] = value
		return db_data

	def _human_to_db ( self , data: dict [ str , Any ] ) -> dict [ str , Any ] :
		"""Преобразует словарь {человеческое_имя: значение} → {имя_бд: значение}."""
		db_data = { }
		for human_name , value in data.items ( ) :
			if human_name in self._column_map :
				db_name = self._column_map [ human_name ].lower ( )
				if isinstance ( value , str ) and self._is_binary_column ( db_name ) :
					try :
						clean = value.replace ( '-' , '' )
						if len ( clean ) == 32 :
							std_uuid = uuid.UUID ( clean )
							value = uuid_1c_to_db ( std_uuid.bytes )
					except (ValueError , AttributeError) :
						pass
				db_data [ db_name ] = value
			else :
				db_data [ human_name.lower ( ) ] = value
		return db_data

	def _is_binary_column ( self , col_name: str ) -> bool :
		"""Проверяет, является ли колонка бинарной."""
		if col_name in self.table.c :
			return isinstance ( self.table.c [ col_name ].type , LargeBinary )
		return False

	# ─── Табличные части ───────────────────────────────

	@property
	def ТабличныеЧасти ( self ) -> list [ str ] :
		"""Список имён табличных частей."""
		return list ( self._children.keys ( ) )

	def Часть ( self , name: str ) -> 'TableQuery' :
		"""Возвращает TableQuery для табличной части по имени."""
		if name in self._children :
			return self._children [ name ]
		raise KeyError (
			f"Табличная часть '{name}' не найдена. Доступные: {list ( self._children.keys ( ) )}" ,
		)

	@validate_call
	def ДобавитьСЧастями (
			self ,
			data: dict [ str , Any ] ,
			части: Optional [ dict [ str , list [ dict [ str , Any ] ] ] ] = None ,
	) -> str :
		"""
		Добавляет запись вместе с табличными частями.

		Args:
				data: словарь {человеческое_имя: значение} для основной записи
				части: словарь {имя_табличной_части: [список_строк]}

		Returns:
				hex-строка нового _idrref основной записи
		"""
		new_id_hex = self.Добавить ( data )
		new_id_bytes = bytes.fromhex ( new_id_hex )
		new_id_1c = uuid_1c_to_db ( new_id_bytes )

		if части :
			for part_name , rows in части.items ( ) :
				if part_name in self._children :
					child = self._children [ part_name ]
					for row in rows :
						# Передаём ссылку на родителя в формате 1С
						child.Добавить (
							row ,
							extra_db_data = { child._owner_key : new_id_1c } ,
						)

		return new_id_hex


class OneSMetadata :
	"""Доступ к объектам 1С с человеческими названиями."""

	@validate_call
	def __init__ ( self , connection_string: str , data_source: str = "postgresql" ) :
		self._client = MetadataClient ( connection_string , data_source )

		params = { }
		for part in connection_string.split ( ';' ) :
			part = part.strip ( )
			if '=' in part :
				key , value = part.split ( '=' , 1 )
				params [ key.lower ( ) ] = value
		url = (
			f"postgresql://{params [ 'username' ]}:{params [ 'password' ]}"
			f"@{params [ 'host' ]}:{params.get ( 'port' , 5432 )}/{params [ 'database' ]}"
		)
		self._engine = create_engine ( url )
		self._inspector = inspect ( self._engine )

		self._cache: dict [ str , dict [ str , TableQuery ] ] = { }
		self._build_cache ( )

	def _build_cache ( self ) :
		"""Строит кэш объектов с человеческими названиями колонок."""
		for type_name in self._client.get_types ( ) :
			self._cache [ type_name ] = { }
			objects = self._client.get_objects ( type_name )

			for obj in objects :
				try :
					result_tuple = self._client._provider.GetMetadataObject ( obj [ 'name' ] )
					if isinstance ( result_tuple , tuple ) :
						entity = result_tuple [ 0 ]
					else :
						entity = result_tuple

					if entity and entity.DbName :
						short_name = (
							obj [ 'name' ].split ( '.' ) [ -1 ]
							if '.' in obj [ 'name' ]
							else obj [ 'name' ]
						)

						column_map: dict [ str , str ] = { }
						primary_key = '_idrref'

						if entity.Properties :
							for prop in entity.Properties :
								human_name = prop.Name
								if prop.Columns and prop.Columns.Count > 0 :
									db_name = prop.Columns [ 0 ].Name
									column_map [ human_name ] = db_name
									if db_name.lower ( ) in ('_idrref' , '_recordkey') :
										primary_key = db_name.lower ( )

						# Табличные части (Entities)
						children: dict [ str , TableQuery ] = { }
						if entity.Entities and entity.Entities.Count > 0 :
							for child_entity in entity.Entities :
								child_name = child_entity.Name
								child_column_map: dict [ str , str ] = { }
								child_pk = '_idrref'
								child_owner_key = None

								if child_entity.Properties :
									for prop in child_entity.Properties :
										child_human_name = prop.Name
										if prop.Columns and prop.Columns.Count > 0 :
											child_db_name = prop.Columns [ 0 ].Name
											child_column_map [ child_human_name ] = child_db_name
											if child_db_name.lower ( ) in ('_idrref' , '_recordkey') :
												child_pk = child_db_name.lower ( )
											# Колонка-ссылка на родителя: заканчивается на _rref И НЕ первичный ключ
											if child_db_name.lower ( ).endswith ( '_rref' ) and child_db_name.lower ( ) != child_pk :
												child_owner_key = child_db_name.lower ( )

								# Если owner_key не найден — ищем любую колонку с 'idrref'
								if child_owner_key is None :
									for col_name in child_column_map.values ( ) :
										if 'idrref' in col_name.lower ( ) and col_name.lower ( ) != child_pk :
											child_owner_key = col_name.lower ( )
											break

								if child_owner_key is None :
									child_owner_key = child_pk  # fallback

								if child_entity.DbName :
									child_table = self._get_table ( child_entity.DbName )

									# Определяем реальный первичный ключ через inspector
									try :
										child_pk_cols = self._inspector.get_pk_constraint (
											child_entity.DbName.lower ( ) ,
										)
										if child_pk_cols and child_pk_cols.get ( 'constrained_columns' ) :
											child_pk = child_pk_cols [ 'constrained_columns' ] [ 0 ]
										else :
											# Если нет PK — используем первую колонку таблицы
											child_pk = list ( child_table.columns.keys ( ) ) [ 0 ]
									except Exception :
										child_pk = list ( child_table.columns.keys ( ) ) [ 0 ]

									children [ child_name ] = TableQuery (
										child_table ,
										self._engine ,
										child_column_map ,
										child_pk ,
										child_owner_key ,
									)

						table = self._get_table ( entity.DbName )
						query = TableQuery (
							table ,
							self._engine ,
							column_map ,
							primary_key ,
							'_idrref' ,
							children ,
						)
						self._cache [ type_name ] [ short_name ] = query
				except Exception :
					pass

	def _get_table ( self , table_name: str ) -> Table :
		"""Создаёт Table-объект через inspector."""
		columns_info = self._inspector.get_columns ( table_name.lower ( ) )
		metadata = MetaData ( )
		columns: list [ Column ] = [ ]

		for col_info in columns_info :
			col_name = col_info [ 'name' ]
			col_type_str = str ( col_info [ 'type' ] ).lower ( )

			col_type = None
			for pg_type , sa_type in TYPE_MAP.items ( ) :
				if pg_type in col_type_str :
					col_type = sa_type
					break
			if col_type is None :
				col_type = String

			columns.append ( Column ( col_name , col_type ) )

		return Table ( table_name.lower ( ) , metadata , *columns )

	def __getattr__ ( self , name: str ) -> 'ObjectTypeAccessor' :
		if name in self._cache :
			return ObjectTypeAccessor ( self._cache [ name ] )
		raise AttributeError (
			f"Type '{name}' not found. Available: {list ( self._cache.keys ( ) )}" ,
		)

	@property
	def типы ( self ) -> list [ str ] :
		"""Список всех типов объектов."""
		return list ( self._cache.keys ( ) )

	@property
	def объекты ( self ) -> dict [ str , list [ str ] ] :
		"""Все объекты всех типов."""
		result = { }
		for type_name , objects in self._cache.items ( ) :
			result [ type_name ] = list ( objects.keys ( ) )
		return result

	def close ( self ) :
		"""Закрывает соединение с БД."""
		self._engine.dispose ( )

	@contextmanager
	def transaction ( self ) :
		"""
		Контекстный менеджер для транзакции.

		Пример:
				with db.transaction():
						db.Справочники['Алгоритмы'].Добавить({...})
						db.Документы['Уведомления'].Добавить({...})
				# Автоматический commit при выходе без ошибок
				# Автоматический rollback при исключении
		"""
		connection = self._engine.connect ( )
		trans = connection.begin ( )

		# Подменяем engine на connection для всех TableQuery
		old_engine = self._engine
		self._engine = connection

		try :
			yield self
			trans.commit ( )
		except Exception :
			trans.rollback ( )
			raise
		finally :
			self._engine = old_engine
			connection.close ( )

	@contextmanager
	def nested_transaction ( self ) :
		"""
		Вложенная транзакция (savepoint).

		Пример:
				with db.transaction():
						db.Справочники['Алгоритмы'].Добавить({...})

						try:
								with db.nested_transaction():
										db.Документы['Уведомления'].Добавить({...})
										raise Exception("Что-то пошло не так")
						except Exception:
								pass  # Откатится только документ

						# Справочник сохранится
		"""
		connection = self._engine if hasattr ( self._engine , 'connect' ) else self._engine
		if hasattr ( connection , 'begin_nested' ) :
			trans = connection.begin_nested ( )
		else :
			# Если это не connection, а engine — создаём savepoint через execute
			trans = None

		try :
			yield self
			if trans :
				trans.commit ( )
		except Exception :
			if trans :
				trans.rollback ( )
			raise

	def savepoint ( self , name: str = None ) -> str :
		"""
		Создаёт точку сохранения (savepoint).

		Args:
				name: имя точки сохранения (автоматическое, если None)

		Returns:
				имя точки сохранения

		Пример:
				sp = db.savepoint("перед_удалением")
				try:
						db.Справочники['Алгоритмы'].Удалить(id)
				except Exception:
						db.rollback_to(sp)
		"""
		import uuid
		sp_name = name or f"sp_{uuid.uuid4 ( ).hex [ :8 ]}"

		connection = self._engine if hasattr ( self._engine , 'connect' ) else self._engine
		connection.execute ( f"SAVEPOINT {sp_name}" )

		return sp_name

	def rollback_to ( self , savepoint: str ) :
		"""
		Откатывает к точке сохранения.

		Args:
				savepoint: имя точки сохранения
		"""
		connection = self._engine if hasattr ( self._engine , 'connect' ) else self._engine
		connection.execute ( f"ROLLBACK TO SAVEPOINT {savepoint}" )

	def commit ( self ) :
		"""Ручной commit текущей транзакции."""
		connection = self._engine if hasattr ( self._engine , 'connect' ) else self._engine
		if hasattr ( connection , 'commit' ) :
			connection.commit ( )

	def rollback ( self ) :
		"""Ручной rollback текущей транзакции."""
		connection = self._engine if hasattr ( self._engine , 'connect' ) else self._engine
		if hasattr ( connection , 'rollback' ) :
			connection.rollback ( )


class ObjectTypeAccessor :
	"""Доступ к объектам одного типа: db.Справочники['Алгоритмы']"""

	def __init__ ( self , objects: dict [ str , TableQuery ] ) :
		self._objects = objects

	def __getitem__ ( self , name: str ) -> TableQuery :
		if name in self._objects :
			return self._objects [ name ]
		raise KeyError (
			f"Object '{name}' not found. Available: {list ( self._objects.keys ( ) )}" ,
		)

	def __getattr__ ( self , name: str ) -> TableQuery :
		if name in self._objects :
			return self._objects [ name ]
		raise AttributeError ( f"Object '{name}' not found" )

	def все ( self ) -> list [ str ] :
		"""Список всех объектов этого типа."""
		return list ( self._objects.keys ( ) )
