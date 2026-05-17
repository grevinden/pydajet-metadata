"""
models.py — Генератор SQLAlchemy-моделей из метаданных 1С.
"""
from sqlalchemy import create_engine , MetaData , Table , Column , Integer , String , DateTime , BINARY , Numeric , \
	Boolean
from sqlalchemy.orm import declarative_base , Session
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base ( )


class MetadataModelGenerator :
	"""Генерирует SQLAlchemy-модели из метаданных 1С."""

	# Маппинг типов 1С → SQLAlchemy
	TYPE_MAPPING = {
		"string"   : String ,
		"binary"   : BINARY ,
		"datetime" : DateTime ,
		"decimal"  : Numeric ,
		"boolean"  : Boolean ,
	}

	def __init__ ( self , client: "MetadataClient" ) :
		self.client = client
		self.engine = None

	def connect ( self , connection_string: str ) :
		"""Подключается к базе данных."""
		# Конвертируем строку 1С в SQLAlchemy URL
		# "Host=localhost;Port=5433;Database=MessageCenter;Username=postgres;Password=qwaseD12;"
		# → "postgresql://postgres:qwaseD12@localhost:5433/MessageCenter"

		params = { }
		for part in connection_string.split ( ';' ) :
			part = part.strip ( )
			if '=' in part :
				key , value = part.split ( '=' , 1 )
				params [ key.lower ( ) ] = value

		url = f"postgresql://{params [ 'username' ]}:{params [ 'password' ]}@{params [ 'host' ]}:{params.get ( 'port' , 5432 )}/{params [ 'database' ]}"
		self.engine = create_engine ( url )

	def _get_column_type ( self , type_str: str ) -> type :
		"""Определяет тип колонки SQLAlchemy по строке типа 1С."""
		if type_str is None :
			return String

		type_str = type_str.lower ( )

		# binary(16,fixed) → Binary(16)
		if type_str.startswith ( "binary" ) :
			import re
			match = re.search ( r'\((\d+)' , type_str )
			size = int ( match.group ( 1 ) ) if match else None
			return BINARY ( size ) if size else BINARY

		# string(150) → String(150)
		if type_str.startswith ( "string" ) :
			import re
			match = re.search ( r'\((\d+)' , type_str )
			size = int ( match.group ( 1 ) ) if match else None
			return String ( size ) if size else String

		# decimal(10,0) → Numeric(10, 0)
		if type_str.startswith ( "decimal" ) :
			import re
			match = re.search ( r'\((\d+),(\d+)\)' , type_str )
			if match :
				return Numeric ( int ( match.group ( 1 ) ) , int ( match.group ( 2 ) ) )
			return Numeric

		# datetime → DateTime
		if type_str.startswith ( "datetime" ) :
			return DateTime

		# boolean → Boolean
		if type_str.startswith ( "boolean" ) or type_str.startswith ( "binary(1,fixed)" ) :
			return Boolean

		return String

	def _get_table_name ( self , object_name: str ) -> str :
		"""Генерирует имя таблицы из имени объекта 1С."""
		# Справочник.Контрагенты → _Reference_Контрагенты
		# Документ.Уведомления → _Document_Уведомления
		# РегистрСведений.ЗначенияПараметров → _InfoReg_ЗначенияПараметров

		prefix_map = {
			"Справочник."             : "_Reference" ,
			"Документ."               : "_Document" ,
			"Константа."              : "_Const" ,
			"Перечисление."           : "_Enum" ,
			"РегистрСведений."        : "_InfoReg" ,
			"РегистрНакопления."      : "_AccumReg" ,
			"РегистрБухгалтерии."     : "_AccReg" ,
			"ПланСчетов."             : "_ChartOfAccounts" ,
			"ПланВидовХарактеристик." : "_ChartOfCharacteristicTypes" ,
			"ПланОбмена."             : "_ExchangePlan" ,
		}

		for prefix , table_prefix in prefix_map.items ( ) :
			if object_name.startswith ( prefix ) :
				name = object_name [ len ( prefix ) : ]
				return f"{table_prefix}_{name}"

		return f"_Unknown_{object_name}"

	def generate_models ( self ) -> dict :
		"""
		Генерирует SQLAlchemy-модели для всех объектов.

		Returns:
				dict: имя таблицы → класс модели
		"""
		models = { }

		for type_name in self.client.get_types ( ) :
			objects = self.client.get_objects ( type_name )

			for obj in objects :
				table_name = self._get_table_name ( obj [ 'name' ] )

				# Собираем все колонки
				columns = [ ]
				has_primary_key = False

				for prop in obj [ 'properties' ] :
					for col in prop.get ( 'columns' , [ ] ) :
						col_name = col [ 'name' ]
						col_type = self._get_column_type ( col [ 'type' ] )

						# Первичный ключ — _IDRRef или _RecordKey
						is_pk = col_name in ('_IDRRef' , '_RecordKey')
						if is_pk :
							has_primary_key = True

						columns.append ( {
							'name' : col_name ,
							'type' : col_type ,
							'pk'   : is_pk ,
						} )

				# Если нет первичного ключа — добавляем авто-id
				if not has_primary_key :
					columns.insert ( 0 , {
						'name' : 'id' ,
						'type' : Integer ,
						'pk'   : True ,
					} )

				# Создаём атрибуты модели
				attrs = {
					'__tablename__'  : table_name ,
					'__table_args__' : { 'extend_existing' : True } ,
				}

				for col in columns :
					if col [ 'pk' ] :
						attrs [ col [ 'name' ] ] = Column ( col [ 'name' ] , col [ 'type' ] , primary_key = True )
					else :
						attrs [ col [ 'name' ] ] = Column ( col [ 'name' ] , col [ 'type' ] )

				# Создаём класс модели
				model_class = type ( table_name , (Base ,) , attrs )
				models [ table_name ] = model_class

		return models
	def create_tables ( self ) :
		"""Создаёт таблицы в базе данных (отражает существующие)."""
		if self.engine :
			Base.metadata.create_all ( self.engine )

	def query ( self , model_class , limit: int = 10 ) -> list :
		"""
		Выполняет запрос к таблице.

		Args:
				model_class: класс модели SQLAlchemy
				limit: количество строк

		Returns:
				list: список строк
		"""
		if not self.engine :
			raise RuntimeError ( "Not connected. Call connect() first." )

		with Session ( self.engine ) as session :
			return session.query ( model_class ).limit ( limit ).all ( )


# ─── Пример использования ─────────────────────────────────
if __name__ == "__main__" :
	# from pydajet_metadata.client import MetadataClient
	#
	# client = MetadataClient (
	# 	connection_string = "Host=localhost;Port=5433;Database=MessageCenter;Username=postgres;Password=qwaseD12;" ,
	# 	data_source = "postgresql"
	# )
	#
	# # Узнать реальное имя таблицы
	# table_name = client.get_table_name ( "Справочник.ирАлгоритмы" )
	# print ( f"Реальное имя таблицы: {table_name}" )
	#
	#
	#
	# generator = MetadataModelGenerator ( client )
	# models = generator.generate_models ( )
	#
	#
	# print ( f"Сгенерировано моделей: {len ( models )}" )
	# for table_name , model in models.items ( ) :
	# 	columns = [ c.name for c in model.__table__.columns ]
	# 	print ( f"  {table_name}: {', '.join ( columns )}" )
	#
	# # Подключаемся и читаем данные
	# generator.connect ( "Host=localhost;Port=5433;Database=MessageCenter;Username=postgres;Password=qwaseD12;" )
	#
	# for table_name , model in models.items ( ) :
	# 	try :
	# 		rows = generator.query ( model , limit = 3 )
	# 		if rows :
	# 			print ( f"\n{table_name}: {len ( rows )} строк" )
	# 			for row in rows :
	# 				print ( f"  {row.__dict__}" )
	# 	except Exception as e :
	# 		print ( f"\n{table_name}: ошибка — {e}" )

	import warnings
	from sqlalchemy import exc as sa_exc

	# Это должно сработать
	warnings.filterwarnings ( 'ignore' , category = sa_exc.SAWarning )

	from sqlalchemy import create_engine , inspect , Table , Column , MetaData , select
	from sqlalchemy.types import Integer , String , Boolean , DateTime , LargeBinary , Float

	# Маппинг типов PostgreSQL → SQLAlchemy
	TYPE_MAP = {
		'bytea'                       : LargeBinary ,
		'integer'                     : Integer ,
		'boolean'                     : Boolean ,
		'timestamp'                   : DateTime ,
		'timestamp without time zone' : DateTime ,
		'character varying'           : String ,
		'mvarchar'                    : String ,
		'varchar'                     : String ,
		'text'                        : String ,
		'numeric'                     : Float ,
		'bigint'                      : Integer ,
		'smallint'                    : Integer ,
		'double precision'            : Float ,
		'real'                        : Float ,
	}


	def get_table ( engine , table_name: str ) -> Table :
		"""Создаёт Table-объект без autoload, через inspector."""
		inspector = inspect ( engine )
		columns_info = inspector.get_columns ( table_name )

		metadata = MetaData ( )
		columns = [ ]

		for col_info in columns_info :
			col_name = col_info [ 'name' ]
			col_type_str = str ( col_info [ 'type' ] ).lower ( )

			# Определяем тип
			col_type = None
			for pg_type , sa_type in TYPE_MAP.items ( ) :
				if pg_type in col_type_str :
					col_type = sa_type
					break

			if col_type is None :
				col_type = String  # По умолчанию

			# Создаём колонку
			col = Column ( col_name , col_type )
			columns.append ( col )

		return Table ( table_name , metadata , *columns )


	# Использование
	engine = create_engine ( 'postgresql://postgres:qwaseD12@localhost:5433/MessageCenter' )
	table = get_table ( engine , '_reference53' )

	print ( f"Колонки: {[ c.name for c in table.columns ]}" )

	with engine.connect ( ) as conn :
		rows = conn.execute ( select ( table ).limit ( 2 ) )
		for row in rows :
			print ( { c.name : getattr ( row , c.name ) for c in table.columns } )
