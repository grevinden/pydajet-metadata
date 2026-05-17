"""
setup.py — сборщик Python-пакета pydajet-metadata.

Алгоритм работы:
  1. Читаем версию DaJet Metadata из pyproject.toml
  2. Проверяем через GitHub API, изменился ли релиз с бинарниками
  3. Если изменился — скачиваем архивы для всех платформ
  4. Распаковываем архивы в src/pydajet_metadata/bin/
  5. Сохраняем состояние релиза для будущих проверок
  6. Setuptools упаковывает всё в wheel

Все платформы скачиваются и распаковываются параллельно.
"""
import importlib.util
import importlib.util
import json
import os
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor , as_completed
from pathlib import Path
from types import ModuleType
from urllib.request import Request , build_opener , HTTPSHandler

from setuptools import Command , setup  # noqa [STATIC]
from setuptools.command.egg_info import egg_info  # noqa [STATIC]

# Глобальный кэш и блокировка для потокобезопасности
_MODULE_CACHE: dict [ str , ModuleType ] = { }
_CACHE_LOCK = threading.Lock ( )

# ---------------------------------------------------------------------------
# Конфигурация
# ---------------------------------------------------------------------------

PATH_ROOT = Path(__file__).parent.resolve()
PATH_SCRIPTS = PATH_ROOT / 'scripts'
PATH_CACHE = PATH_ROOT / ".dajet_cache"
PATH_BIN_IN_SRC = PATH_ROOT / "src" / "pydajet_metadata" / "bin"
STATE_FILE = PATH_CACHE / "release_state.json"

GITHUB_REPO = "grevinden/dajet-metadata"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/download"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags"

PLATFORMS = [
    "win-x64", "win-arm64",
    "linux-x64", "linux-arm64",
    "osx-x64", "osx-arm64",
]

MAX_WORKERS = 6


def script ( name: str ) -> ModuleType :
    """
    Загружает Python-модуль из файла с кэшированием.
    Повторные вызовы для одного пути возвращают тот же объект без перезагрузки.
    """
    abs_path = str ( PATH_SCRIPTS / Path ( name ).with_suffix ( '.py' ) )

    # 🚀 Fast path без блокировки
    if abs_path in _MODULE_CACHE :
        return _MODULE_CACHE [ abs_path ]

    with _CACHE_LOCK :
        # 🔒 Double-checked locking
        if abs_path in _MODULE_CACHE :
            return _MODULE_CACHE [ abs_path ]

        # Генерируем уникальное имя для sys.modules (чтобы не конфликтовать с другими модулями)
        module_name = f"_cached_{hash ( abs_path ) & 0xFFFFFFFF:08x}"

        spec = importlib.util.spec_from_file_location ( module_name , abs_path )
        if not spec or not spec.loader :
            raise ImportError ( f"Не удалось создать спецификацию для {name}" )

        module = importlib.util.module_from_spec ( spec )
        sys.modules [ module_name ] = module  # ✅ Нужно для корректных относительных импортов

        try :
            spec.loader.exec_module ( module )
        except Exception as e :
            # 🧹 Очистка кэша при ошибке, чтобы не хранить "сломанные" модули
            _MODULE_CACHE.pop ( abs_path , None )
            sys.modules.pop ( module_name , None )
            raise ImportError ( f"Ошибка выполнения модуля {name}: {e}" ) from e

        _MODULE_CACHE [ abs_path ] = module
        return module


# ---------------------------------------------------------------------------
# Версия
# ---------------------------------------------------------------------------

def read_dajet_version ( ) -> str :
    """Читает версию DaJet Metadata из секции [tool.dajet] в pyproject.toml."""
    pyproject = PATH_ROOT / "pyproject.toml"
    try :
        import tomllib
    except ImportError :
        import tomli as tomllib
    with open ( pyproject , "rb" ) as f :
        return tomllib.load ( f ) [ "tool" ] [ "dajet" ] [ "version" ]


def is_windows_platform ( platform_name: str ) -> bool :
    """Определяет, относится ли платформа к Windows по имени."""
    return platform_name.startswith ( "win" )


# ---------------------------------------------------------------------------
# Состояние релиза (GitHub API + локальный кэш)
# ---------------------------------------------------------------------------

def get_remote_release_state ( ) -> dict | None :
    """Запрашивает GitHub API и возвращает состояние релиза."""
    version = read_dajet_version ( )
    url = f"{API_URL}/{version}"

    try :
        req = Request ( url )
        req.add_header ( "Accept" , "application/vnd.github+json" )
        req.add_header ( "User-Agent" , "pydajet-metadata" )

        token = os.environ.get ( "GITHUB_TOKEN" )
        if token :
            req.add_header ( "Authorization" , f"Bearer {token}" )

        opener = build_opener ( HTTPSHandler )
        with opener.open ( req ) as r :
            if r.status == 200 :
                data = json.loads ( r.read ( ) )
                return {
                    "tag"          : data.get ( "tag_name" ) ,
                    "published_at" : data.get ( "published_at" ) ,
                    "assets"       : [
                        {
                            "name"       : a.get ( "name" ) ,
                            "size"       : a.get ( "size" ) ,
                            "updated_at" : a.get ( "updated_at" ) ,
                        }
                        for a in data.get ( "assets" , [ ] )
                    ] ,
                }
            else :
                print ( f"  GitHub API returned {r.status}" )
                return None
    except Exception as e :
        print ( f"  Failed to check release state: {e}" )
        return None


def get_local_release_state ( ) -> dict | None :
    """Читает сохранённое состояние релиза из кэша."""
    if STATE_FILE.exists ( ) :
        try :
            return json.loads ( STATE_FILE.read_text ( ) )
        except json.JSONDecodeError :
            return None
    return None


def save_release_state ( state: dict ) -> None :
    """Сохраняет состояние релиза в кэш."""
    PATH_CACHE.mkdir ( parents = True , exist_ok = True )
    STATE_FILE.write_text ( json.dumps ( state , indent = 2 ) )


def is_release_changed ( ) -> bool :
    """Сравнивает локальное состояние релиза с удалённым."""
    local = get_local_release_state ( )
    if local is None :
        return True

    remote = get_remote_release_state ( )
    if remote is None :
        print ( "  Could not check remote release, assuming unchanged" )
        return False

    if local.get ( "published_at" ) != remote.get ( "published_at" ) :
        return True

    local_assets = { a [ "name" ] : a [ "size" ] for a in local.get ( "assets" , [ ] ) }
    remote_assets = { a [ "name" ] : a [ "size" ] for a in remote.get ( "assets" , [ ] ) }
    return local_assets != remote_assets


# ---------------------------------------------------------------------------
# Загрузка одного файла
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, retries: int = 3) -> bool:
    """Скачивает файл с докачкой и ретраями."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        return True

    temp = dest.with_suffix(dest.suffix + '.part')
    initial = temp.stat().st_size if temp.exists() else 0
    headers = {'Range': f'bytes={initial}-'} if initial > 0 else {}

    for attempt in range(retries):
        try:
            req = Request(url, headers=headers)
            opener = build_opener ( HTTPSHandler )
            with opener.open ( req ) as r :
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
                return True
        except Exception :
            if attempt == retries - 1:
                raise
            continue

    return False


# ---------------------------------------------------------------------------
# Обработка одной платформы (в потоке)
# ---------------------------------------------------------------------------

def process_platform ( platform_name: str , version: str ) -> str :
    """Скачивает и распаковывает одну платформу."""
    artifact = f"dajet-metadata-{platform_name}"
    ext = "zip" if is_windows_platform ( platform_name ) else "tar.gz"
    url = f"{RELEASES_URL}/{version}/{artifact}.{ext}"
    archive_path = PATH_CACHE / f"{artifact}.{ext}"
    extract_path = PATH_BIN_IN_SRC / platform_name

    print ( f"  [{platform_name}] Downloading..." )
    if not download_file ( url , archive_path ) :
        raise RuntimeError ( f"Failed to download {platform_name}" )

    print ( f"  [{platform_name}] Extracting..." )

    script ( 'archive' ).ArchiveExtractor (
        archive_path , extract_path
    ).extract_all ( )

    archive_path.unlink ( )
    print ( f"  [{platform_name}] Done" )
    return platform_name


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def download_all_binaries ( ) -> None :
    """Точка входа: проверяет релиз, качает и распаковывает все платформы."""
    version = read_dajet_version ( )
    print ( "=" * 50 )
    print ( f"Downloading DaJet Metadata {version}" )
    print ( f"Target: {PATH_BIN_IN_SRC}" )
    print ( f"Platforms: {', '.join ( PLATFORMS )}" )
    print ( f"Workers: {MAX_WORKERS}" )
    print("=" * 50)

    # Проверяем, все ли платформы на месте
    missing = [
        p for p in PLATFORMS
        if not (PATH_BIN_IN_SRC / p).exists ( ) or not any ( (PATH_BIN_IN_SRC / p).iterdir ( ) )
    ]

    if missing :
        print ( f"Missing platforms: {', '.join ( missing )}" )
        print ( "Downloading missing platforms..." )
    elif not is_release_changed ( ) :
        print ( f"Release {version} hasn't changed, skipping download" )
        print ( "=" * 50 )
        return
    else :
        print ( f"Release {version} has changed, removing old binaries..." )
        for platform_name in PLATFORMS :
            platform_path = PATH_BIN_IN_SRC / platform_name
            if platform_path.exists ( ) :
                shutil.rmtree ( platform_path )

    PATH_BIN_IN_SRC.mkdir ( parents = True , exist_ok = True )

    # Параллельная загрузка
    errors = [ ]
    with ThreadPoolExecutor ( max_workers = MAX_WORKERS ) as executor :
        futures = {
            executor.submit ( process_platform , p , version ) : p
            for p in PLATFORMS
        }
        for future in as_completed ( futures ) :
            platform = futures [ future ]
            try :
                future.result ( )
            except Exception as e :
                errors.append ( (platform , str ( e )) )
                print ( f"  [{platform}] FAILED: {e}" )

    if errors :
        print ( "\n" + "=" * 50 )
        print ( "Errors occurred:" )
        for platform , error in errors :
            print ( f"  {platform}: {error}" )
        raise RuntimeError ( f"Failed to download {len ( errors )} platform(s)" )

    # Сохраняем состояние
    remote_state = get_remote_release_state ( )
    if remote_state :
        save_release_state ( remote_state )
        print ( "Release state saved" )

    print ( "=" * 50 )


# ---------------------------------------------------------------------------
# Команды setuptools
# ---------------------------------------------------------------------------

class EggInfoWithDownload(egg_info):
    """Перед генерацией egg-info вызывает загрузку бинарников."""
    def run(self):
        download_all_binaries()
        super().run()


class DownloadCommand(Command):
    """Ручная команда: python setup.py download"""
    description = "Download DaJet Metadata binaries"

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        download_all_binaries()
        print ( f"Binaries in {PATH_BIN_IN_SRC}" )


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

setup(
    cmdclass={
        "egg_info": EggInfoWithDownload,
        "download": DownloadCommand,
    },
)
