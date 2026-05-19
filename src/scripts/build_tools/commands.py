from __future__ import annotations

import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request

from setuptools import Command
from setuptools.command.egg_info import egg_info

from .config import BuildConfig
from .downloader import DownloadTask, FileDownloader
from .logging_utils import get_logger

logger = get_logger("commands")


def read_dajet_version(root_path: Path | None = None) -> str:
    pyproject = (Path(root_path) if root_path is not None else Path(__file__).resolve().parents[2]) / "pyproject.toml"
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    with pyproject.open("rb") as stream:
        data = tomllib.load(stream)
    return data["tool"]["dajet"]["version"]


def get_remote_release_state(config: BuildConfig) -> dict | None:
    version = read_dajet_version(config.root_path)
    url = f"{config.api_url}/{version}"

    req = Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "pydajet-metadata")

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    opener = config.build_opener()
    with opener.open(req, timeout=config.http_timeout) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            logger.warning("GitHub API returned %s", status)
            return None
        payload = json.loads(response.read().decode("utf-8"))

    return {
        "tag": payload.get("tag_name"),
        "published_at": payload.get("published_at"),
        "assets": [
            {
                "name": asset.get("name"),
                "size": asset.get("size"),
                "updated_at": asset.get("updated_at"),
            }
            for asset in payload.get("assets", [])
        ],
    }


def get_local_release_state(config: BuildConfig) -> dict | None:
    if config.state_file.exists():
        try:
            return json.loads(config.state_file.read_text("utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def save_release_state(config: BuildConfig, state: dict) -> None:
    config.cache_path.mkdir(parents=True, exist_ok=True)
    config.state_file.write_text(json.dumps(state, indent=2), "utf-8")


def is_release_changed(config: BuildConfig) -> bool:
    local = get_local_release_state(config)
    if local is None:
        return True

    remote = get_remote_release_state(config)
    if remote is None:
        logger.info("Could not check remote release state, assuming unchanged")
        return False

    if local.get("published_at") != remote.get("published_at"):
        return True

    local_assets = {item["name"]: item["size"] for item in local.get("assets", [])}
    remote_assets = {item["name"]: item["size"] for item in remote.get("assets", [])}
    return local_assets != remote_assets


def download_platform(config: BuildConfig, version: str, platform_name: str) -> str:
    artifact = f"dajet-metadata-{platform_name}"
    ext = "zip" if config.is_windows_platform(platform_name) else "tar.gz"
    url = f"{config.releases_url}/{version}/{artifact}.{ext}"
    archive_path = config.cache_path / f"{artifact}.{ext}"
    destination = config.bin_dir / platform_name

    downloader = FileDownloader(config)
    archive_path = downloader.download(DownloadTask(url=url, destination=archive_path))

    from scripts.archive import ArchiveExtractor

    try:
        ArchiveExtractor(archive_path, destination).extract_all()
    except Exception:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        raise
    finally:
        archive_path.unlink(missing_ok=True)

    return platform_name


def download_all_binaries(
    config: BuildConfig | None = None,
    force: bool = False,
) -> BuildConfig:
    resolved = config or BuildConfig.load()
    resolved.cache_path.mkdir(parents=True, exist_ok=True)
    resolved.bin_dir.mkdir(parents=True, exist_ok=True)

    version = read_dajet_version(resolved.root_path)
    logger.info("Preparing DaJet Metadata binaries for version %s", version)

    missing = [
        platform
        for platform in resolved.platforms
        if not (resolved.bin_dir / platform).exists()
        or not any((resolved.bin_dir / platform).iterdir())
    ]

    if missing:
        logger.info("Missing platforms: %s", ", ".join(missing))
    elif not force and not is_release_changed(resolved):
        logger.info("Release %s unchanged, skipping binary download", version)
        return resolved
    else:
        if not missing:
            logger.info("Release %s changed, cleaning existing binaries", version)
            for platform in resolved.platforms:
                platform_path = resolved.bin_dir / platform
                if platform_path.exists():
                    shutil.rmtree(platform_path)

    errors: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=resolved.max_workers) as executor:
        futures = {executor.submit(download_platform, resolved, version, platform): platform for platform in resolved.platforms}
        for future in as_completed(futures):
            platform = futures[future]
            try:
                future.result()
            except Exception as exc:
                logger.error("Download failed for %s: %s", platform, exc)
                errors.append((platform, str(exc)))

    if errors:
        raise RuntimeError(f"Failed to download {len(errors)} platform(s): {errors}")

    remote_state = get_remote_release_state(resolved)
    if remote_state:
        save_release_state(resolved, remote_state)
        logger.info("Release state saved to %s", resolved.state_file)

    return resolved


class EggInfoWithDownload(egg_info):
    """Ensure DaJet binaries are synchronized before egg-info is generated."""

    def run(self) -> None:
        logger.info("Running egg_info with binary synchronization")
        download_all_binaries()
        super().run()


class DownloadCommand(Command):
    """Custom setuptools command: python setup.py download"""

    description = "Download DaJet Metadata binaries"
    user_options: list[tuple[str, str | None, str]] = [
        ("force", None, "Force binary download even if the release state is unchanged"),
    ]

    force: bool | None = None

    def initialize_options(self) -> None:
        self.force = False

    def finalize_options(self) -> None:
        self.force = bool(self.force)

    def run(self) -> None:
        logger.info("Running explicit download command")
        config = download_all_binaries(force=self.force)
        print(f"Binaries synchronized in {config.bin_dir}")
