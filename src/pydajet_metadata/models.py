"""
models.py — Динамические Pydantic-модели из метаданных 1С.
Поддерживает табличные части, валидацию, сериализацию.
"""
from typing import Optional , Any , ClassVar
from datetime import datetime
from pydantic import BaseModel , Field , create_model , field_validator


class OneSModelGenerator :
	"""Генератор Pydantic-моделей из метаданных 1С."""

	TYPE_MAP = {
		'string'   : str ,
		'datetime' : datetime ,
		'decimal'  : float ,
		'boolean'  : bool ,
		'binary'   : bytes ,
		'integer'  : int ,
	}

	def __init__ ( self , orm: 'OneSMetadata' ) :
		self._orm = orm
		self._models: dict [ str , type [ BaseModel ] ] = { }
		self._generate_all ( )

	def _generate_all ( self ) :
		"""Генерирует модели для всех объектов."""
		for type_name in self._orm.типы :
			accessor = getattr ( self._orm , type_name )
			for obj_name in accessor.все ( ) :
				query = accessor [ obj_name ]

				# Генерируем модели для табличных частей
				child_models = { }
				for child_name in query.ТабличныеЧасти :
					child_query = query.Часть ( child_name )
					child_model = self._create_model ( child_name , child_query , is_child = True )
					child_models [ child_name ] = child_model

				# Генерируем основную модель
				model = self._create_model (
					f"{type_name}.{obj_name}" ,
					query ,
					children = child_models ,
				)
				self._models [ f"{type_name}.{obj_name}" ] = model

	def _create_model (
			self ,
			name: str ,
			query: 'TableQuery' ,
			children: dict [ str , type [ BaseModel ] ] = None ,
			is_child: bool = False ,
	) -> type [ BaseModel ] :
		"""Создаёт Pydantic-модель из TableQuery."""
		fields = { }
		validators = { }

		for human_name , db_name in query._column_map.items ( ) :
			col = query.table.c [ db_name.lower ( ) ]
			py_type = self._get_python_type ( col )

			# Ссылка — первичный ключ
			if db_name.lower ( ) == query._primary_key :
				fields [ human_name ] = (Optional [ str ] , Field ( default = None , description = "UUID записи" ))
			elif not col.nullable and db_name.lower ( ) != query._owner_key :
				fields [ human_name ] = (py_type , Field ( ... ))
			else :
				fields [ human_name ] = (Optional [ py_type ] , Field ( default = None ))

		# Добавляем табличные части как поля
		if children :
			for child_name , child_model in children.items ( ) :
				fields [ child_name ] = (Optional [ list [ child_model ] ] , Field ( default_factory = list ))

		# Создаём модель
		model = create_model (
			name.split ( '.' ) [ -1 ] if '.' in name else name ,
			**fields ,
			__module__ = __name__ ,
		)

		# Привязываем query и children
		model._query = ClassVar [ Any ] = query
		model._children_models = ClassVar [ dict ] = children or { }
		model._is_child = ClassVar [ bool ] = is_child

		# ─── Методы модели ─────────────────────────

		@classmethod
		def from_db ( cls , record_id: str ) :
			"""Загружает запись из БД по ID."""
			row = query.where (
				query.table.c [ query._primary_key ] == bytes.fromhex ( record_id )
			).first ( )
			if row :
				# Загружаем табличные части
				if children :
					for child_name , child_model in children.items ( ) :
						child_query = query.Часть ( child_name )
						child_rows = child_query.where (
							child_query.table.c [ child_query._owner_key ] == bytes.fromhex ( record_id )
						).all ( )
						row [ child_name ] = [ child_model ( **r ) for r in child_rows ]

				return cls ( **row )
			return None

		model.from_db = classmethod ( from_db )

		def save ( self ) :
			"""Сохраняет модель в БД."""
			data = self.model_dump ( exclude_none = True )

			# Извлекаем табличные части
			parts = { }
			for child_name in query.ТабличныеЧасти :
				if child_name in data and data [ child_name ] :
					parts [ child_name ] = [
						item.model_dump ( exclude_none = True ) if isinstance ( item , BaseModel ) else item
						for item in data [ child_name ]
					]
				data.pop ( child_name , None )

			pk_value = data.get ( 'Ссылка' )

			if pk_value :
				query.Изменить ( pk_value , data )
			else :
				pk_value = query.Добавить ( data )
				self.Ссылка = pk_value

			# Сохраняем табличные части
			if parts :
				# Удаляем старые записи табличных частей
				for child_name in parts :
					child_query = query.Часть ( child_name )
					# Удаляем все строки, связанные с этой записью
					child_query.Удалить ( pk_value )

				# Добавляем новые
				query.ДобавитьСЧастями ( data , parts )

			return self

		model.save = save

		def delete ( self ) :
			"""Удаляет запись из БД."""
			if self.Ссылка :
				# Сначала удаляем табличные части
				for child_name in query.ТабличныеЧасти :
					child_query = query.Часть ( child_name )
					child_query.Удалить ( self.Ссылка )

				query.Удалить ( self.Ссылка )
				self.Ссылка = None
			return self

		model.delete = delete

		@classmethod
		def all ( cls ) :
			"""Возвращает все записи."""
			rows = query.all ( )
			return [ cls ( **row ) for row in rows ]

		model.all = classmethod ( all )

		@classmethod
		def where ( cls , *conditions ) :
			"""Возвращает записи по условию."""
			rows = query.where ( *conditions ).all ( )
			return [ cls ( **row ) for row in rows ]

		model.where = classmethod ( where )

		@classmethod
		def first ( cls ) :
			"""Возвращает первую запись."""
			row = query.first ( )
			return cls ( **row ) if row else None

		model.first = classmethod ( first )

		@classmethod
		def count ( cls ) :
			"""Возвращает количество записей."""
			return query.count ( )

		model.count = classmethod ( count )

		return model

	def _get_python_type ( self , col ) -> type :
		"""Определяет Python-тип из SQLAlchemy-колонки."""
		col_type = str ( col.type ).lower ( )

		for db_type , py_type in self.TYPE_MAP.items ( ) :
			if db_type in col_type :
				return py_type

		return str

	def get_model ( self , name: str ) -> type [ BaseModel ] :
		"""Возвращает модель по имени (например, 'Справочники.ирАлгоритмы')."""
		return self._models.get ( name )

	def get_all_models ( self ) -> dict [ str , type [ BaseModel ] ] :
		"""Возвращает все сгенерированные модели."""
		return self._models

	def model ( self , name: str ) -> type [ BaseModel ] :
		"""Краткий доступ к модели."""
		return self._models [ name ]


# ─── Пример использования ─────────────────────────────────
if __name__ == "__main__" :
	from orm import OneSMetadata

	db = OneSMetadata (
		"Host=localhost;Port=5433;Database=MessageCenter;Username=postgres;Password=qwaseD12;"
	)

	# Генерируем все модели
	gen = OneSModelGenerator ( db )

	# ─── Справочник ───────────────────────────────────
	Алгоритм = gen.model ( "Справочники.ирАлгоритмы" )

	# Создать
	alg = Алгоритм (
		Наименование = "Тестовый" ,
		ТекстАлгоритма = 'Сообщить("Привет");' ,
		ДатаИзменения = datetime.now ( ) ,
	)
	alg.save ( )
	print ( f"Создан справочник: {alg.Ссылка}" )

	# Загрузить
	alg2 = Алгоритм.from_db ( alg.Ссылка )
	print ( f"Загружен: {alg2.Наименование}" )

	# Изменить
	alg2.Наименование = "Обновлённый"
	alg2.save ( )

	# Все записи
	for a in Алгоритм.all ( ) :
		print ( f"  {a.Наименование}: {a.ТекстАлгоритма [ :50 ]}..." )

	# Удалить
	alg2.delete ( )

	# ─── Документ с табличной частью ─────────────────
	Уведомление = gen.model ( "Документы.Уведомления" )

	# Создать документ с табличной частью
	doc = Уведомление (
		Дата = datetime.now ( ) ,
		Номер = "0000001" ,
		Проведен = True ,
		Сообщение = "Тестовое уведомление" ,
	)

	# Добавляем строки табличной части
	Получатель = gen._models [ "Получатели" ]  # Модель табличной части
	doc.Получатели = [
		Получатель ( Сотрудник = "Иванов" , Статус = "Новый" ) ,
		Получатель ( Сотрудник = "Петров" , Статус = "Прочитано" ) ,
	]

	doc.save ( )
	print ( f"Создан документ: {doc.Ссылка}" )

	# Загрузить с табличной частью
	doc2 = Уведомление.from_db ( doc.Ссылка )
	print ( f"Загружен документ: {doc2.Номер}" )
	print ( f"  Получателей: {len ( doc2.Получатели )}" )
	for p in doc2.Получатели :
		print ( f"    {p.Сотрудник}: {p.Статус}" )

	db.close ( )
