"""Поиск бинарников .NET."""
import platform
from pathlib import Path


def find_binary_folder ( ) -> Path :
	"""Находит папку с бинарниками DaJet Metadata для текущей ОС."""
	system = platform.system ( ).lower ( )
	machine = platform.machine ( ).lower ( )

	os_map = { "windows" : "win" , "linux" : "linux" , "darwin" : "osx" }
	arch_map = { "x86_64" : "x64" , "amd64" : "x64" , "arm64" : "arm64" , "aarch64" : "arm64" }

	bin_folder = Path (
		__file__ ).parent.parent / "pydajet_metadata" / "bin" / f"{os_map [ system ]}-{arch_map [ machine ]}"

	if not bin_folder.exists ( ) :
		raise FileNotFoundError ( f"Binary folder not found: {bin_folder}" )

	return bin_folder
