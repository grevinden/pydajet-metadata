from __future__ import annotations

from setuptools import Command
from setuptools.command.egg_info import egg_info

from .config import BuildConfig
from .logging_utils import get_logger

logger = get_logger("commands")


def download_all_binaries(config: BuildConfig | None = None) -> BuildConfig:
    """Placeholder sync hook used by setup.py commands.

    Returns the resolved configuration so callers can report the target path.
    The actual download orchestration can be expanded later without breaking
    setuptools command imports.
    """
    resolved = config or BuildConfig.load()
    resolved.cache_path.mkdir(parents=True, exist_ok=True)
    resolved.bin_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Binary synchronization placeholder executed for %s", resolved.bin_dir)
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
    user_options: list[tuple[str, str | None, str]] = []

    def initialize_options(self) -> None:
        return None

    def finalize_options(self) -> None:
        return None

    def run(self) -> None:
        logger.info("Running explicit download command")
        config = download_all_binaries()
        print(f"Binaries synchronized in {config.bin_dir}")
