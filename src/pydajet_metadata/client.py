from pydajet_metadata import DataSourceType,List,Guid,MetadataProvider


class MetadataClient :
	"""Клиент для чтения метаданных 1С."""

	# Префиксы имён объектов → типы метаданных
	_PREFIX_MAP = {
		"Справочник."             : "Справочники" ,
		"Документ."               : "Документы" ,
		"Константа."              : "Константы" ,
		"Перечисление."           : "Перечисления" ,
		"ПланВидовХарактеристик." : "ПланыВидовХарактеристик" ,
		"РегистрСведений."        : "РегистрыСведений" ,
		"РегистрНакопления."      : "РегистрыНакопления" ,
		"РегистрБухгалтерии."     : "РегистрыБухгалтерии" ,
		"ПланСчетов."             : "ПланыСчетов" ,
		"ПланОбмена."             : "ПланыОбмена" ,
		"ОпределяемыйТип."        : "ОпределяемыеТипы" ,
		"Задача."                 : "Задачи" ,
		"БизнесПроцесс."          : "БизнесПроцессы" ,
	}

	def __init__ ( self , connection_string: str , data_source: str = "postgresql" ) :
		"""
		Args:
				connection_string: строка подключения к БД
				data_source: 'postgresql' или 'sqlserver'
		"""
		ds_map = {
			"postgresql" : DataSourceType.PostgreSql ,
			"sqlserver"  : DataSourceType.SqlServer ,
		}
		data_source_type = ds_map [ data_source.lower ( ) ]

		result = MetadataProvider.Create ( data_source_type , connection_string )
		self._provider = result [ 0 ]
		self._config = self._provider.GetConfigurations ( ) [ 0 ]

		# Строим карту UUID типа → имя типа на основе имён объектов
		self._uuid_to_type = self._build_uuid_type_map ( )

	# ─── Внутренние методы ───────────────────────────────

	def _get_type_by_name ( self , name: str ) -> str :
		"""Определяет тип метаданных по полному имени объекта."""
		for prefix , type_name in self._PREFIX_MAP.items ( ) :
			if name.startswith ( prefix ) :
				return type_name
		return "Неизвестный"

	def _build_uuid_type_map ( self ) -> dict :
		"""
		Строит карту UUID типа → имя типа на основе реальных имён объектов.
		Для каждого UUID загружаем имена объектов и определяем тип по префиксу.
		"""
		uuid_map = { }
		for type_uuid in self._config.Metadata.Keys :
			guids = self._config.Metadata [ type_uuid ]
			if len ( guids ) == 0 :
				continue

			# Получаем имена объектов
			entity_list = List [ Guid ] ( )
			for i in range ( len ( guids ) ) :
				entity_list.Add ( guids [ i ] )

			names , _ = self._provider.ResolveReferences ( entity_list )

			# Определяем тип по первому имени
			if names.Count > 0 and names [ 0 ] :
				type_name = self._get_type_by_name ( names [ 0 ] )
				uuid_map [ type_uuid ] = type_name

		return uuid_map

	def _get_uuids_for_type ( self , type_uuid: Guid ) -> List [ Guid ] :
		"""Создаёт List[Guid] из массива Guid[] для указанного типа."""
		guids = self._config.Metadata [ type_uuid ]
		entity_list = List [ Guid ] ( )
		for i in range ( len ( guids ) ) :
			entity_list.Add ( guids [ i ] )
		return entity_list

	# ─── Свойства конфигурации ───────────────────────────

	@property
	def configuration_name ( self ) -> str :
		"""Имя конфигурации."""
		return self._config.Name

	@property
	def configuration_alias ( self ) -> str :
		"""Синоним конфигурации."""
		return self._config.Alias

	@property
	def platform_version ( self ) -> int :
		"""Версия платформы."""
		return self._config.PlatformVersion

	@property
	def year_offset ( self ) -> int :
		"""Год смещения дат."""
		return self._config.YearOffset

	# ─── Список типов объектов ───────────────────────────

	def get_types ( self ) -> list [ str ] :
		"""Возвращает список типов объектов, присутствующих в конфигурации."""
		return sorted ( set ( self._uuid_to_type.values ( ) ) )

	# ─── Список объектов по типу ─────────────────────────

	def get_objects ( self , type_name: str ) -> list [ dict ] :
		"""
		Возвращает список объектов метаданных указанного типа.

		Args:
				type_name: 'Справочники', 'Документы', 'РегистрыСведений' и т.д.

		Returns:
				list[dict]: список словарей с ключами:
						- name: полное имя объекта (например, "Справочник.Контрагенты")
						- type: тип метаданных
						- properties: список реквизитов [{'name': ..., 'columns': [...]}]
		"""
		result = [ ]

		for type_uuid , detected_type in self._uuid_to_type.items ( ) :
			if detected_type != type_name :
				continue

			entity_list = self._get_uuids_for_type ( type_uuid )
			names , _ = self._provider.ResolveReferences ( entity_list )

			for i in range ( names.Count ) :
				name = names [ i ]
				if not name :
					continue

				obj_info = {
					"name"       : name ,
					"type"       : type_name ,
					"properties" : [ ] ,
				}

				try :
					obj_tuple = self._provider.GetMetadataObject ( name )
					if isinstance ( obj_tuple , tuple ) :
						obj = obj_tuple [ 0 ]
					else :
						obj = obj_tuple

					if obj and obj.Properties and obj.Properties.Count > 0 :
						for prop in obj.Properties :
							prop_info = { "name" : prop.Name , "columns" : [ ] }
							if prop.Columns and prop.Columns.Count > 0 :
								for col in prop.Columns :
									prop_info [ "columns" ].append ( {
										"name" : col.Name ,
										"type" : str ( col.Type ) if col.Type else None ,
									} )
							obj_info [ "properties" ].append ( prop_info )
				except Exception :
					pass  # Для определяемых типов GetMetadataObject не реализован

				result.append ( obj_info )

			break  # Нашли нужный тип — выходим

		return result

	def get_all_objects ( self ) -> dict [ str , list [ dict ] ] :
		"""
		Возвращает все объекты метаданных, сгруппированные по типам.

		Returns:
				dict: ключи — названия типов, значения — списки объектов
		"""
		result = { }
		for type_name in self.get_types ( ) :
			objects = self.get_objects ( type_name )
			if objects :
				result [ type_name ] = objects
		return result


	def get_table_name ( self , object_name: str ) -> str :
		"""
		Возвращает реальное имя таблицы в БД для объекта метаданных.
		"""
		result_tuple = self._provider.GetMetadataObject ( object_name )
		if isinstance ( result_tuple , tuple ) :
			obj = result_tuple [ 0 ]
		else :
			obj = result_tuple

		if obj and obj.DbName :
			return obj.DbName
		return None

# ─── Пример использования ─────────────────────────────────
# if __name__ == "__main__" :
# 	client = MetadataClient (
# 		connection_string = "Host=localhost;Port=5433;Database=MessageCenter;Username=postgres;Password=qwaseD12;" ,
# 		data_source = "postgresql" ,
# 	)
#
# 	print ( f"Конфигурация: {client.configuration_name}" )
# 	print ( f"Платформа: {client.platform_version}" )
# 	print ( f"Типы объектов: {client.get_types ( )}" )
# 	print ( )
#
# 	for type_name in client.get_types ( ) :
# 		objects = client.get_objects ( type_name )
# 		print ( f"\n{type_name} ({len ( objects )}):" )
# 		for obj in objects :
# 			props = [ p [ 'name' ] for p in obj [ 'properties' ] ]
# 			print ( f"  {obj [ 'name' ]}: {', '.join ( props ) if props else 'нет реквизитов'}" )
