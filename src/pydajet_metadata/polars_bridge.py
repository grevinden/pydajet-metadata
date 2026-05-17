"""
polars_bridge.py — Интеграция Polars ↔ 1С.
Чтение/запись целых таблиц через DataFrame.
"""
from typing import Optional
import polars as pl
from datetime import datetime


class OneSPolarsBridge :
	"""Мост между OneSMetadata и Polars DataFrame."""

	def __init__ ( self , orm: 'OneSMetadata' ) :
		self._orm = orm

	# ─── Чтение в Polars ──────────────────────────────

	def read ( self , type_name: str , object_name: str ) -> pl.DataFrame :
		"""
		Читает все записи объекта 1С в Polars DataFrame.

		Args:
				type_name: тип объекта ('Справочники', 'Документы', ...)
				object_name: имя объекта ('ирАлгоритмы', ...)

		Returns:
				Polars DataFrame с человеческими названиями колонок
		"""
		accessor = getattr ( self._orm , type_name )
		query = accessor [ object_name ]
		rows = query.all ( )

		if not rows :
			# Возвращаем пустой DataFrame с правильной схемой
			schema = { name : self._get_polars_type ( query , name ) for name in query._column_map }
			schema.update ( { child : pl.List ( pl.Struct ( [ ] ) ) for child in query.ТабличныеЧасти } )
			return pl.DataFrame ( schema = schema )

		# Загружаем табличные части
		for child_name in query.ТабличныеЧасти :
			child_query = query.Часть ( child_name )
			child_rows = child_query.all ( )

			# Группируем по владельцу
			child_by_owner = { }
			for row in child_rows :
				owner_id = row.get ( child_query._owner_key ) or row.get ( '_document209_idrref' )
				if owner_id :
					child_by_owner.setdefault ( owner_id , [ ] ).append ( row )

			# Присоединяем к основным строкам
			for row in rows :
				pk = row.get ( 'Ссылка' )
				if pk :
					row [ child_name ] = child_by_owner.get ( pk , [ ] )

		return pl.DataFrame ( rows )

	def _get_polars_type ( self , query , col_name: str ) -> pl.DataType :
		"""Определяет Polars-тип для колонки."""
		col = query.table.c [ query._column_map [ col_name ].lower ( ) ]
		col_type = str ( col.type ).lower ( )

		if 'string' in col_type or 'varchar' in col_type :
			return pl.Utf8
		elif 'datetime' in col_type or 'timestamp' in col_type :
			return pl.Datetime
		elif 'bool' in col_type :
			return pl.Boolean
		elif 'int' in col_type :
			return pl.Int64
		elif 'float' in col_type or 'decimal' in col_type or 'numeric' in col_type :
			return pl.Float64
		elif 'bytea' in col_type or 'binary' in col_type :
			return pl.Utf8  # UUID храним как hex-строку

		return pl.Utf8

	# ─── Запись из Polars ─────────────────────────────

	def write (
			self ,
			df: pl.DataFrame ,
			type_name: str ,
			object_name: str ,
			mode: str = 'replace' ,
	) -> int :
		"""
		Записывает Polars DataFrame в таблицу 1С.

		Args:
				df: Polars DataFrame с данными
				type_name: тип объекта
				object_name: имя объекта
				mode: 'replace' (удалить всё и вставить) или 'append' (добавить)

		Returns:
				количество записанных строк
		"""
		accessor = getattr ( self._orm , type_name )
		query = accessor [ object_name ]

		if mode == 'replace' :
			# Удаляем все существующие записи
			existing = query.all ( )
			for row in existing :
				pk = row.get ( 'Ссылка' )
				if pk :
					query.Удалить ( pk )

		# Преобразуем DataFrame в список словарей
		rows = df.to_dicts ( )
		count = 0

		for row in rows :
			# Извлекаем табличные части
			parts = { }
			for child_name in query.ТабличныеЧасти :
				if child_name in row and row [ child_name ] :
					parts [ child_name ] = row [ child_name ]
				row.pop ( child_name , None )

			if parts :
				query.ДобавитьСЧастями ( row , parts )
			else :
				query.Добавить ( row )

			count += 1

		return count

	# ─── Аналитика с Polars ───────────────────────────

	def analytics ( self , type_name: str , object_name: str ) -> 'Analytics' :
		"""Возвращает объект для аналитических операций."""
		df = self.read ( type_name , object_name )
		return Analytics ( df , self , type_name , object_name )


class Analytics :
	"""Аналитические операции над таблицей 1С через Polars."""

	def __init__ ( self , df: pl.DataFrame , bridge: 'OneSPolarsBridge' , type_name: str , object_name: str ) :
		self.df = df
		self._bridge = bridge
		self._type_name = type_name
		self._object_name = object_name

	def filter ( self , *conditions ) -> 'Analytics' :
		"""Фильтрует DataFrame."""
		self.df = self.df.filter ( *conditions )
		return self

	def select ( self , *columns: str ) -> 'Analytics' :
		"""Выбирает колонки."""
		self.df = self.df.select ( *columns )
		return self

	def sort ( self , by: str , descending: bool = False ) -> 'Analytics' :
		"""Сортирует DataFrame."""
		self.df = self.df.sort ( by , descending = descending )
		return self

	def group_by ( self , *columns: str ) -> 'Analytics' :
		"""Группирует DataFrame."""
		self.df = self.df.group_by ( *columns ).len ( )
		return self

	def join ( self , other: 'Analytics' , on: str , how: str = 'inner' ) -> 'Analytics' :
		"""Объединяет с другим DataFrame."""
		self.df = self.df.join ( other.df , on = on , how = how )
		return self

	def collect ( self ) -> pl.DataFrame :
		"""Возвращает DataFrame."""
		return self.df

	def to_dicts ( self ) -> list [ dict ] :
		"""Возвращает список словарей."""
		return self.df.to_dicts ( )

	def count ( self ) -> int :
		"""Количество строк."""
		return self.df.height

	def write_back ( self , mode: str = 'replace' ) -> int :
		"""Записывает DataFrame обратно в БД."""
		return self._bridge.write ( self.df , self._type_name , self._object_name , mode )


# ─── Пример использования ─────────────────────────────────
if __name__ == "__main__" :
	from orm import OneSMetadata

	db = OneSMetadata (
		"Host=localhost;Port=5433;Database=MessageCenter;Username=postgres;Password=qwaseD12;"
	)

	bridge = OneSPolarsBridge ( db )

	# ─── Чтение всей таблицы ──────────────────────────
	df = bridge.read ( "Справочники" , "ирАлгоритмы" )
	print ( f"Загружено {df.height} записей" )
	print ( df.head ( 2 ) )

	# ─── Аналитика ────────────────────────────────────
	analytics = bridge.analytics ( "Справочники" , "ирАлгоритмы" )

	# Фильтрация
	filtered = analytics.filter (
		pl.col ( "Наименование" ).str.contains ( "telegram" )
	).collect ( )
	print ( f"\nОтфильтровано: {filtered.height} записей" )

	# Группировка
	grouped = analytics.group_by ( "ДатаИзменения" ).sort ( "len" , descending = True )
	print ( f"\nГруппировка по дате: {grouped.collect ( )}" )

	# ─── Пакетная вставка ────────────────────────────
	new_data = pl.DataFrame ( [
		{
			"Наименование"   : "Алгоритм 1" ,
			"ТекстАлгоритма" : 'Сообщить("Привет");' ,
			"ДатаИзменения"  : datetime.now ( ) ,
		} ,
		{
			"Наименование"   : "Алгоритм 2" ,
			"ТекстАлгоритма" : 'Сообщить("Пока");' ,
			"ДатаИзменения"  : datetime.now ( ) ,
		} ,
	] )

	count = bridge.write ( new_data , "Справочники" , "ирАлгоритмы" , mode = "append" )
	print ( f"\nВставлено {count} записей" )

	# Проверяем
	df = bridge.read ( "Справочники" , "ирАлгоритмы" )
	print ( f"Всего записей: {df.height}" )
	print ( df [ [ "Наименование" , "ТекстАлгоритма" ] ] )

	# ─── Массовое обновление ──────────────────────────
	df = bridge.read ( "Справочники" , "ирАлгоритмы" )

	# Изменяем данные в DataFrame
	df = df.with_columns (
		pl.when ( pl.col ( "Наименование" ) == "Алгоритм 1" )
		.then ( pl.lit ( "Обновлённый алгоритм 1" ) )
		.otherwise ( pl.col ( "Наименование" ) )
		.alias ( "Наименование" )
	)

	# Записываем обратно
	bridge.write ( df , "Справочники" , "ирАлгоритмы" , mode = "replace" )
	print ( f"\nОбновлено записей: {df.height}" )

	db.close ( )
