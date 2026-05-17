import platform
from functools import cache
from pathlib import Path

@cache
def find_binary_folder ( ) -> Path :
	"""
	Определяет папку с бинарниками DaJet Metadata для текущей ОС и архитектуры.

	Returns:
			Path: путь к папке вида .../bin/win-x64/

	Raises:
			FileNotFoundError: если папка не найдена
			OSError: если ОС или архитектура не поддерживаются
	"""
	system = platform.system ( ).lower ( )
	machine = platform.machine ( ).lower ( )

	# Определяем ОС
	os_map = {
		"windows" : "win" ,
		"linux"   : "linux" ,
		"darwin"  : "osx" ,
	}
	if system not in os_map :
		raise OSError ( f"Unsupported OS: {system}" )
	os_name = os_map [ system ]

	# Определяем архитектуру
	arch_map = {
		"x86_64"  : "x64" ,
		"amd64"   : "x64" ,
		"arm64"   : "arm64" ,
		"aarch64" : "arm64" ,
	}
	if machine not in arch_map :
		raise OSError ( f"Unsupported architecture: {machine}" )
	arch = arch_map [ machine ]

	# Ищем папку с бинарниками
	bin_dir = (Path ( __file__ ).parent / "bin" / f"{os_name}-{arch}").resolve()

	if not bin_dir.exists ( ) :
		raise FileNotFoundError (
			f"Binary folder not found: {bin_dir}\n"
			f"Expected structure: pydajet_metadata/bin/{os_name}-{arch}/"
		)

	return bin_dir
