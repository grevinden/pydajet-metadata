"""
client.py — Низкоуровневый доступ к метаданным 1С.
"""
from typing import Optional

from pydajet_metadata import MetadataProvider , DataSourceType , Guid , List


class MetadataClient :
	"""Клиент для чтения метаданных 1С через DaJet Metadata."""

	PREFIX_MAP = {
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
		ds = DataSourceType.PostgreSql if data_source == "postgresql" else DataSourceType.SqlServer
		result = MetadataProvider.Create ( ds , connection_string )
		self._provider = result [ 0 ]
		self._config = self._provider.GetConfigurations ( ) [ 0 ]
		self._type_map = self._build_type_map ( )

	def _build_type_map ( self ) -> dict [ Guid , str ] :
		"""UUID типа → имя типа."""
		type_map = { }
		for type_uuid in self._config.Metadata.Keys :
			guids = self._config.Metadata [ type_uuid ]
			if len ( guids ) == 0 :
				continue

			entity_list = List [ Guid ] ( )
			for i in range ( len ( guids ) ) :
				entity_list.Add ( guids [ i ] )

			names , _ = self._provider.ResolveReferences ( entity_list )
			if names.Count > 0 and names [ 0 ] :
				type_map [ type_uuid ] = self._prefix_to_type ( names [ 0 ] )

		return type_map

	@classmethod
	def _prefix_to_type ( cls , name: str ) -> str :
		for prefix , type_name in cls.PREFIX_MAP.items ( ) :
			if name.startswith ( prefix ) :
				return type_name
		return "Неизвестный"

	@property
	def config_name ( self ) -> str :
		return self._config.Name

	@property
	def config_alias ( self ) -> Optional [ str ] :
		return self._config.Alias

	def list_types ( self ) -> list [ str ] :
		return sorted ( set ( self._type_map.values ( ) ) )

	def list_objects ( self , type_name: str ) -> list [ dict ] :
		"""Возвращает список объектов с метаданными."""
		result = [ ]

		for type_uuid , detected_type in self._type_map.items ( ) :
			if detected_type != type_name :
				continue

			guids = self._config.Metadata [ type_uuid ]
			entity_list = List [ Guid ] ( )
			for i in range ( len ( guids ) ) :
				entity_list.Add ( guids [ i ] )

			names , _ = self._provider.ResolveReferences ( entity_list )

			for i in range ( names.Count ) :
				name = names [ i ]
				if not name :
					continue

				entity = self._get_entity ( name )
				if not entity :
					continue

				obj = {
					'name'       : name ,
					'short_name' : name.split ( '.' ) [ -1 ] if '.' in name else name ,
					'table'      : entity.DbName ,
					'properties' : self._extract_properties ( entity ) ,
					'children'   : self._extract_children ( entity ) ,
				}
				result.append ( obj )

			break

		return result

	def _get_entity ( self , name: str ) :
		try :
			result = self._provider.GetMetadataObject ( name )
			return result [ 0 ] if isinstance ( result , tuple ) else result
		except Exception :
			return None

	def _extract_properties ( self , entity ) -> list [ dict ] :
		props = [ ]
		if entity.Properties :
			for prop in entity.Properties :
				columns = [ ]
				if prop.Columns and prop.Columns.Count > 0 :
					for col in prop.Columns :
						columns.append ( {
							'name' : col.Name ,
							'type' : str ( col.Type ) if col.Type else None ,
						} )
				props.append ( { 'name' : prop.Name , 'columns' : columns } )
		return props

	def _extract_children ( self , entity ) -> list [ dict ] :
		children = [ ]
		if entity.Entities and entity.Entities.Count > 0 :
			for child in entity.Entities :
				children.append ( {
					'name'       : child.Name ,
					'table'      : child.DbName ,
					'properties' : self._extract_properties ( child ) ,
				} )
		return children
