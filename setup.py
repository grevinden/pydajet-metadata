import os
import shutil
import tarfile
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request

from setuptools import setup, Command
from setuptools.command.egg_info import egg_info


def read_dajet_version() -> str:
    pyproject = Path(__file__).parent / "pyproject.toml"
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    with open(pyproject, "rb") as f:
        return tomllib.load(f)["tool"]["dajet"]["version"]


# Используем временную папку внутри проекта, которая будет доступна в любом окружении
PATH_ROOT = Path(__file__).parent.resolve()
PATH_CACHE = PATH_ROOT / ".dajet_cache"  # Локальный кэш архивов
PATH_BIN_IN_SRC = PATH_ROOT / "src" / "pydajet_metadata" / "bin"  # Цель

GITHUB_REPO = "grevinden/dajet-metadata"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/download"
DAJET_VERSION = read_dajet_version()

PLATFORMS = [
    "win-x64", "win-arm64",
    "linux-x64", "linux-arm64",
    "osx-x64", "osx-arm64",
]


def download_file(url: str, dest: Path, retries: int = 3) -> bool:
    print(f"  Downloading: {url}")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"  Already exists: {dest}")
        return True

    temp = dest.with_suffix(dest.suffix + '.part')
    initial = temp.stat().st_size if temp.exists() else 0
    headers = {'Range': f'bytes={initial}-'} if initial > 0 else {}

    for attempt in range(retries):
        try:
            req = Request(url, headers=headers)
            with urlopen(req) as r:
                if r.status == 416:
                    temp.unlink(missing_ok=True)
                    return download_file(url, dest, retries)

                if r.status >= 400:
                    body = r.read(200).decode(errors='replace')
                    raise RuntimeError(f"HTTP {r.status}: {body}")

                mode = 'ab' if initial > 0 else 'wb'
                with open(temp, mode) as f:
                    f.write(r.read())

                temp.replace(dest)
                print(f"  ✅ Downloaded: {dest.name}")
                return True
        except Exception as e:
            print(f"  ⚠️ Attempt {attempt + 1} failed: {e}")
            if attempt == retries - 1:
                raise
            continue

    return False


def download_all_binaries():
    """Скачать и распаковать все платформы ПРЯМО в src/pydajet_metadata/bin/"""
    print("=" * 50)
    print(f"Downloading DaJet Metadata v{DAJET_VERSION}")
    print(f"Target: {PATH_BIN_IN_SRC}")
    print("=" * 50)

    PATH_BIN_IN_SRC.mkdir(parents=True, exist_ok=True)

    for platform_name in PLATFORMS:
        artifact = f"dajet-metadata-{platform_name}"
        ext = "zip" if platform_name.startswith("win") else "tar.gz"
        url = f"{RELEASES_URL}/{DAJET_VERSION}/{artifact}.{ext}"
        archive_path = PATH_CACHE / f"{artifact}.{ext}"
        extract_path = PATH_BIN_IN_SRC / platform_name

        if extract_path.exists() and any(extract_path.iterdir()):
            print(f"⏭️  {platform_name} (already exists)")
            continue

        if download_file(url, archive_path):
            print(f"📦 Extracting {platform_name} -> {extract_path}")
            extract_path.mkdir(parents=True, exist_ok=True)

            if ext == "zip":
                with zipfile.ZipFile(archive_path) as z:
                    for member in z.namelist():
                        parts = member.split('/', 1)
                        if len(parts) > 1 and parts[1]:
                            target = extract_path / parts[1]
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with z.open(member) as src, open(target, 'wb') as dst:
                                dst.write(src.read())
            else:
                with tarfile.open(archive_path) as tf:
                    for member in tf.getmembers():
                        parts = member.name.split('/', 1)
                        if len(parts) > 1 and parts[1]:
                            member.name = parts[1]
                            tf.extract(member, extract_path)

            archive_path.unlink()
            print(f"✅ {platform_name}")

    print("=" * 50)


class EggInfoWithDownload(egg_info):
    """Скачивает бинарники ПРЯМО в src/ перед генерацией egg-info"""
    def run(self):
        download_all_binaries()
        super().run()


class DownloadCommand(Command):
    description = "Download DaJet Metadata binaries"

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        download_all_binaries()
        print(f"✅ Binaries in {PATH_BIN_IN_SRC}")


setup(
    cmdclass={
        "egg_info": EggInfoWithDownload,
        "download": DownloadCommand,
    },
)
