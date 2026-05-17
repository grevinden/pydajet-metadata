"""
openapi_generator.py — Генератор OpenAPI/FastAPI из метаданных 1С.
Создаёт готовое REST API для всех объектов 1С.
"""
from typing import Optional , Any
from datetime import datetime
from fastapi import FastAPI , HTTPException , Query
from pydantic import BaseModel , Field , create_model
import uvicorn


class OpenAPIGenerator :
	"""Генерирует FastAPI-приложение из метаданных 1С."""

	def __init__ ( self , orm: 'OneSMetadata' , title: str = "1С REST API" ) :
		self._orm = orm
		self._app = FastAPI (
			title = title ,
			description = "Автоматически сгенерированное REST API для 1С" ,
			version = "1.0.0" ,
		)
		self._bridge = None  # Polars bridge (ленивая загрузка)
		self._models = { }  # Сгенерированные Pydantic-модели

	@property
	def app ( self ) -> FastAPI :
		"""Возвращает готовое FastAPI-приложение."""
		return self._app

	def generate_all ( self ) :
		"""Генерирует endpoints для всех объектов."""
		# Генерируем модели
		self._generate_models ( )

		# Генерируем endpoints
		self._generate_crud_endpoints ( )
		self._generate_analytics_endpoints ( )
		self._generate_info_endpoints ( )

		return self._app

	def _generate_models ( self ) :
		"""Генерирует Pydantic-модели для всех объектов."""
		from pydantic import create_model

		for type_name in self._orm.типы :
			accessor = getattr ( self._orm , type_name )
			for obj_name in accessor.все ( ) :
				query = accessor [ obj_name ]

				# Модель для ответа
				response_fields = { }
				for human_name , db_name in query._column_map.items ( ) :
					col = query.table.c [ db_name.lower ( ) ]
					py_type = self._get_python_type ( col )
					response_fields [ human_name ] = (Optional [ py_type ] , Field ( default = None ))

				response_model = create_model (
					f"{type_name}_{obj_name}Response" ,
					**response_fields ,
				)

				# Модель для создания
				create_fields = { }
				for human_name , db_name in query._column_map.items ( ) :
					if db_name.lower ( ) in (query._primary_key , '_version' , '_marked') :
						continue  # Пропускаем служебные поля
					col = query.table.c [ db_name.lower ( ) ]
					py_type = self._get_python_type ( col )
					if not col.nullable :
						create_fields [ human_name ] = (py_type , Field ( ... ))
					else :
						create_fields [ human_name ] = (Optional [ py_type ] , Field ( default = None ))

				create_model_cls = create_model (
					f"{type_name}_{obj_name}Create" ,
					**create_fields ,
				)

				# Модель для обновления (все поля опциональные)
				update_fields = { }
				for human_name , db_name in query._column_map.items ( ) :
					if db_name.lower ( ) in (query._primary_key ,) :
						continue
					col = query.table.c [ db_name.lower ( ) ]
					py_type = self._get_python_type ( col )
					update_fields [ human_name ] = (Optional [ py_type ] , Field ( default = None ))

				update_model = create_model (
					f"{type_name}_{obj_name}Update" ,
					**update_fields ,
				)

				self._models [ f"{type_name}/{obj_name}" ] = {
					'query'     : query ,
					'response'  : response_model ,
					'create'    : create_model_cls ,
					'update'    : update_model ,
					'type_name' : type_name ,
					'obj_name'  : obj_name ,
				}

	def _generate_crud_endpoints ( self ) :
		"""Генерирует CRUD endpoints."""

		for key , model_data in self._models.items ( ) :
			type_name = model_data [ 'type_name' ]
			obj_name = model_data [ 'obj_name' ]
			query = model_data [ 'query' ]
			ResponseModel = model_data [ 'response' ]
			CreateModel = model_data [ 'create' ]
			UpdateModel = model_data [ 'update' ]

			prefix = f"/{type_name}/{obj_name}"

			# GET /{type_name}/{obj_name} — все записи
			@self._app.get (
				f"{prefix}" ,
				response_model = list [ ResponseModel ] ,
				tags = [ type_name ] ,
				summary = f"Получить все {obj_name}" ,
			)
			def get_all (
					skip: int = Query ( 0 , description = "Пропустить N записей" ) ,
					limit: int = Query ( 100 , description = "Ограничить количество" ) ,
			) :
				rows = query.all ( )
				# Конвертируем словари в Pydantic-модели
				return [ ResponseModel ( **row ) for row in rows [ skip :skip + limit ] ]

			# GET /{type_name}/{obj_name}/{id} — запись по ID
			@self._app.get (
				f"{prefix}/{{record_id}}" ,
				response_model = ResponseModel ,
				tags = [ type_name ] ,
				summary = f"Получить {obj_name} по ID" ,
			)
			def get_by_id ( record_id: str ) :
				row = query.where (
					query.table.c [ query._primary_key ] == bytes.fromhex ( record_id )
				).first ( )
				if not row :
					raise HTTPException ( status_code = 404 , detail = "Запись не найдена" )
				return ResponseModel ( **row )

			# POST /{type_name}/{obj_name} — создать запись
			@self._app.post (
				f"{prefix}" ,
				response_model = ResponseModel ,
				tags = [ type_name ] ,
				summary = f"Создать {obj_name}" ,
			)
			def create ( data: CreateModel ) :
				new_id = query.Добавить ( data.model_dump ( exclude_none = True ) )
				row = query.where (
					query.table.c [ query._primary_key ] == bytes.fromhex ( new_id )
				).first ( )
				return ResponseModel ( **row )

			# PUT /{type_name}/{obj_name}/{id} — обновить запись
			@self._app.put (
				f"{prefix}/{{record_id}}" ,
				response_model = ResponseModel ,
				tags = [ type_name ] ,
				summary = f"Обновить {obj_name}" ,
			)
			def update ( record_id: str , data: UpdateModel ) :
				updated = query.Изменить ( record_id , data.model_dump ( exclude_none = True ) )
				if not updated :
					raise HTTPException ( status_code = 404 , detail = "Запись не найдена" )
				row = query.where (
					query.table.c [ query._primary_key ] == bytes.fromhex ( record_id )
				).first ( )
				return ResponseModel ( **row )

			# DELETE /{type_name}/{obj_name}/{id} — удалить запись
			@self._app.delete (
				f"{prefix}/{{record_id}}" ,
				tags = [ type_name ] ,
				summary = f"Удалить {obj_name}" ,
			)
			def delete ( record_id: str ) :
				deleted = query.Удалить ( record_id )
				if not deleted :
					raise HTTPException ( status_code = 404 , detail = "Запись не найдена" )
				return { "status" : "deleted" }

			# GET /{type_name}/{obj_name}/count — количество записей
			@self._app.get (
				f"{prefix}/count" ,
				tags = [ type_name ] ,
				summary = f"Количество {obj_name}" ,
			)
			def count ( ) :
				return { "count" : query.count ( ) }
	def _generate_analytics_endpoints ( self ) :
		"""Генерирует аналитические endpoints через Polars."""
		if not self._bridge :
			from pydajet_metadata.polars_bridge import OneSPolarsBridge
			self._bridge = OneSPolarsBridge ( self._orm )

		@self._app.get (
			"/analytics/{type_name}/{obj_name}/stats" ,
			tags = [ "Аналитика" ] ,
			summary = "Статистика по объекту" ,
		)
		def get_stats ( type_name: str , obj_name: str ) :
			df = self._bridge.read ( type_name , obj_name )
			if df.height == 0 :
				return { "count" : 0 }

			stats = { "count" : df.height }

			# Статистика по колонкам
			for col in df.columns :
				if df [ col ].dtype in (pl.Float64 , pl.Int64) :
					stats [ col ] = {
						"min"  : df [ col ].min ( ) ,
						"max"  : df [ col ].max ( ) ,
						"mean" : df [ col ].mean ( ) ,
					}
				elif df [ col ].dtype == pl.Datetime :
					stats [ col ] = {
						"min" : str ( df [ col ].min ( ) ) ,
						"max" : str ( df [ col ].max ( ) ) ,
					}
				elif df [ col ].dtype == pl.Utf8 :
					stats [ col ] = {
						"unique" : df [ col ].n_unique ( ) ,
					}

			return stats

		@self._app.get (
			"/analytics/{type_name}/{obj_name}/group/{column}" ,
			tags = [ "Аналитика" ] ,
			summary = "Группировка по колонке" ,
		)
		def get_grouped ( type_name: str , obj_name: str , column: str ) :
			df = self._bridge.read ( type_name , obj_name )
			if column not in df.columns :
				raise HTTPException ( status_code = 400 , detail = f"Колонка '{column}' не найдена" )

			grouped = df.group_by ( column ).len ( ).sort ( "len" , descending = True )
			return grouped.to_dicts ( )

	def _generate_info_endpoints ( self ) :
		"""Генерирует информационные endpoints."""

		@self._app.get (
			"/info/types" ,
			tags = [ "Информация" ] ,
			summary = "Список типов объектов" ,
		)
		def get_types ( ) :
			return self._orm.типы

		@self._app.get (
			"/info/objects/{type_name}" ,
			tags = [ "Информация" ] ,
			summary = "Список объектов типа" ,
		)
		def get_objects ( type_name: str ) :
			if type_name not in self._orm.типы :
				raise HTTPException ( status_code = 404 , detail = f"Тип '{type_name}' не найден" )
			accessor = getattr ( self._orm , type_name )
			return accessor.все ( )

		@self._app.get (
			"/info/tables/{type_name}/{obj_name}" ,
			tags = [ "Информация" ] ,
			summary = "Структура таблицы" ,
		)
		def get_table_info ( type_name: str , obj_name: str ) :
			try :
				accessor = getattr ( self._orm , type_name )
				query = accessor [ obj_name ]
			except (KeyError , AttributeError) :
				raise HTTPException ( status_code = 404 , detail = "Объект не найден" )

			columns = { }
			for human_name , db_name in query._column_map.items ( ) :
				col = query.table.c [ db_name.lower ( ) ]
				columns [ human_name ] = {
					"db_name"  : db_name ,
					"type"     : str ( col.type ) ,
					"nullable" : col.nullable ,
				}

			return {
				"name"     : obj_name ,
				"table"    : query.table.name ,
				"columns"  : columns ,
				"children" : query.ТабличныеЧасти ,
			}

	def _get_python_type ( self , col ) -> type :
		"""Определяет Python-тип из SQLAlchemy-колонки."""
		col_type = str ( col.type ).lower ( )

		if 'string' in col_type or 'varchar' in col_type :
			return str
		elif 'datetime' in col_type or 'timestamp' in col_type :
			return datetime
		elif 'bool' in col_type :
			return bool
		elif 'int' in col_type :
			return int
		elif 'float' in col_type or 'decimal' in col_type or 'numeric' in col_type :
			return float
		elif 'bytea' in col_type or 'binary' in col_type :
			return str  # UUID как hex-строка

		return str

	def run ( self , host: str = "0.0.0.0" , port: int = 8000 ) :
		"""Запускает HTTP-сервер."""
		uvicorn.run ( self._app , host = host , port = port )


# ─── Пример использования ─────────────────────────────────
if __name__ == "__main__" :
	from orm import OneSMetadata

	db = OneSMetadata (
		"Host=localhost;Port=5433;Database=MessageCenter;Username=postgres;Password=qwaseD12;"
	)

	# Генерируем API
	generator = OpenAPIGenerator ( db , title = "MessageCenter API" )
	app = generator.generate_all ( )

	# Запускаем сервер
	# http://localhost:8000/docs — Swagger UI
	# http://localhost:8000/redoc — ReDoc
	generator.run ( )
