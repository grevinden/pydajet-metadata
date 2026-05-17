import shutil
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import List


class ArchiveExtractor :
	"""
    Универсальный распаковщик.
    - ZIP: Распаковывает структуру 'как есть' (без обрезки корней).
    - TAR.GZ: Если в корне одна папка, она автоматически обрезается.
    """

	def __init__ ( self , archive_path: Path , dest_path: Path ) -> None :
		self.archive_path = archive_path.resolve ( )
		self.dest_path = dest_path.resolve ( )

		if not self.archive_path.exists ( ) :
			raise FileNotFoundError ( f"❌ Архив не найден: {self.archive_path}" )

		# Корректное определение составных расширений (.tar.gz, .tar.bz2 и т.д.)
		self.suffix = "".join ( self.archive_path.suffixes ).lower ( )

	def extract_all ( self ) -> None :
		"""Запускает процесс распаковки."""
		if self.dest_path.exists ( ) :
			shutil.rmtree ( self.dest_path , ignore_errors = True )
		self.dest_path.mkdir ( parents = True , exist_ok = True )

		if self.suffix == '.zip' :
			self._extract_zip ( )
		elif self.suffix == '.tar.gz' :
			self._extract_tar_gz ( )
		else :
			raise ValueError ( f"❌ Неподдерживаемый формат: {self.suffix}" )

	# =========================================================================
	# ZIP: Распаковка БЕЗ обрезки (как есть)
	# =========================================================================
	def _extract_zip ( self ) -> None :
		with zipfile.ZipFile ( self.archive_path ) as zf :
			zf.extractall ( path= self.dest_path )

	# =========================================================================
	# TAR.GZ: Умная обрезка корня
	# =========================================================================
	def _extract_tar_gz ( self ) -> None :
		with tarfile.open ( self.archive_path , 'r:*' ) as tf :
			members = tf.getmembers ( )
			if not members :
				return

			# Проверяем, нужно ли обрезать корень
			root_prefix = self._get_single_root_prefix ( members )

			if root_prefix :
				processed = [ ]
				prefix_len = len ( root_prefix )
				for m in members :
					# Пропускаем саму корневую папку
					if m.name == root_prefix or m.name == f"{root_prefix}/" :
						continue

					if m.name.startswith ( root_prefix ) :
						m.name = m.name [ prefix_len : ]
						# В tar директории должны заканчиваться на '/'
						if m.isdir ( ) and not m.name.endswith ( "/" ) :
							m.name += "/"
						processed.append ( m )
				members_to_extract = processed
			else :
				# Плоский архив или несколько корней -> без обрезки
				members_to_extract = members

			kwargs = { "path" : str ( self.dest_path ) , "members" : members_to_extract }
			if sys.version_info >= (3 , 12) :
				kwargs [ "filter" ] = "data"
			tf.extractall ( **kwargs )

	# =========================================================================
	# УТИЛИТЫ
	# =========================================================================
	@staticmethod
	def _get_single_root_prefix ( members: List [ tarfile.TarInfo ] ) -> str :
		"""Возвращает имя корневой папки с '/', если в архиве ровно один корневой элемент."""
		roots = set ( )
		for m in members :
			if m.name :
				# Берём первый компонент пути (до первого '/')
				roots.add ( m.name.split ( "/" ) [ 0 ] )

		# Если ровно один корневой элемент → это папка-обёртка
		if len ( roots ) == 1 :
			return roots.pop ( ) + "/"
		return ""
