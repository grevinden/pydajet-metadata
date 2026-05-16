import tarfile
import zipfile
from pathlib import Path

from setuptools import setup, Command
from setuptools.command.build_py import build_py


def read_dajet_version() -> str:
    pyproject = Path(__file__).parent / "pyproject.toml"
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    with open(pyproject, "rb") as f:
        return tomllib.load(f)["tool"]["dajet"]["version"]


PATH_ROOT = Path(__file__).parent.resolve()
PATH_CACHE = PATH_ROOT / "build" / ".cache"
PATH_BIN = PATH_ROOT / "src" / "dajet_metadata" / "bin"

GITHUB_REPO = "grevinden/dajet-metadata"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/download"
DAJET_VERSION = read_dajet_version()

PLATFORMS = [
    "win-x64", "win-arm64",
    "linux-x64", "linux-arm64",
    "osx-x64", "osx-arm64",
]


def download_file(url: str, dest: Path, retries: int = 3) -> bool:
    # Импорт внутри функции — не нужен при парсинге setup.py
    from httpx import Client

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return True

    temp = dest.with_suffix(dest.suffix + '.part')
    initial = temp.stat().st_size if temp.exists() else 0
    headers = {'Range': f'bytes={initial}-'} if initial > 0 else {}

    for attempt in range(retries):
        try:
            with Client() as client:
                with client.stream('GET', url, headers=headers, follow_redirects=True) as r:
                    if r.status_code == 416:
                        temp.unlink(missing_ok=True)
                        return download_file(url, dest, retries)

                    if r.status_code >= 400:
                        body = r.read(200).decode(errors='replace')
                        raise RuntimeError(f"HTTP {r.status_code}: {body}")

                    mode = 'ab' if initial > 0 else 'wb'
                    with open(temp, mode) as f:
                        for chunk in r.iter_bytes():
                            f.write(chunk)

                    temp.replace(dest)
                    return True
        except Exception:
            if attempt == retries - 1:
                raise
            continue

    return False


def download_all_binaries():
    PATH_BIN.mkdir(parents=True, exist_ok=True)

    for platform_name in PLATFORMS:
        artifact = f"dajet-metadata-{platform_name}"
        ext = "zip" if platform_name.startswith("win") else "tar.gz"
        url = f"{RELEASES_URL}/{DAJET_VERSION}/{artifact}.{ext}"
        archive_path = PATH_CACHE / f"{artifact}.{ext}"
        extract_path = PATH_BIN / artifact

        if extract_path.exists() and any(extract_path.iterdir()):
            print(f"⏭️  {artifact}")
            continue

        if download_file(url, archive_path):
            print(f"Extracting {artifact}...")
            extract_path.mkdir(parents=True, exist_ok=True)
            if ext == "zip":
                with zipfile.ZipFile(archive_path) as z:
                    z.extractall(extract_path)
            else:
                with tarfile.open(archive_path) as tf:
                    tf.extractall(extract_path)
            archive_path.unlink()
            print(f"✅ {artifact}")


class BuildPyWithDownload(build_py):
    def run(self):
        download_all_binaries()
        super().run()


class DownloadCommand(Command):
    description = "Download DaJet Metadata binaries for all platforms"

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        download_all_binaries()


setup(
    cmdclass={
        "build_py": BuildPyWithDownload,
        "download": DownloadCommand,
    },
)
