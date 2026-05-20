"""
setup.py — bootstrap installer для пакета pydajet-metadata.

Этот файл выполняет минимальную работу:
- загружает build tooling из scripts/build_tools
- запускает синхронизацию бинарников при установке и при генерации egg-info
- оставляет метаданные пакета в pyproject.toml
"""

from __future__ import annotations

from setuptools import setup, find_packages
from setuptools.command.develop import develop
from setuptools.command.install import install

try:
    from scripts.build_tools import DownloadCommand, EggInfoWithDownload, download_all_binaries  # type: ignore
except Exception:
    DownloadCommand = None
    EggInfoWithDownload = None
    download_all_binaries = None


class InstallWithDownload(install):
    def run(self) -> None:
        if download_all_binaries is not None:
            try:
                download_all_binaries()
            except Exception:
                # Don't fail installation during isolated builds; just warn
                print("Warning: binary synchronization failed or unavailable; continuing install")
        super().run()


class DevelopWithDownload(develop):
    def run(self) -> None:
        if download_all_binaries is not None:
            try:
                download_all_binaries()
            except Exception:
                print("Warning: binary synchronization failed or unavailable; continuing develop")
        super().run()


cmdclass = {}
if EggInfoWithDownload is not None:
    cmdclass["egg_info"] = EggInfoWithDownload
if DownloadCommand is not None:
    cmdclass["download"] = DownloadCommand
cmdclass["install"] = InstallWithDownload
cmdclass["develop"] = DevelopWithDownload

packages = find_packages(where="src")
# Also include top-level "scripts" package if present (tests import it directly)
scripts_pkgs = find_packages(where=".", include=["scripts", "scripts.*"])
if scripts_pkgs:
    packages.extend(scripts_pkgs)

setup(packages=packages, cmdclass=cmdclass)
