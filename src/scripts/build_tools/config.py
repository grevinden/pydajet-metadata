from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.request import HTTPSHandler, build_opener

DEFAULT_PLATFORMS = (
    "win-x64",
    "win-arm64",
    "linux-x64",
    "linux-arm64",
    "osx-x64",
    "osx-arm64",
)


@dataclass(frozen=True)
class BuildConfig:
    root_path: Path
    github_repo: str = "grevinden/dajet-metadata"
    max_workers: int = 6
    http_timeout: int = 60
    platforms: tuple[str, ...] = DEFAULT_PLATFORMS

    @property
    def scripts_path(self) -> Path:
        return self.root_path / "scripts"

    @property
    def cache_path(self) -> Path:
        return self.root_path / ".dajet_cache"

    @property
    def package_bin_path(self) -> Path:
        return self.root_path / "src" / "pydajet_metadata" / "bin"

    @property
    def bin_dir(self) -> Path:
        return self.package_bin_path

    @property
    def state_file(self) -> Path:
        return self.cache_path / "release_state.json"

    @property
    def releases_url(self) -> str:
        return f"https://github.com/{self.github_repo}/releases/download"

    @property
    def api_url(self) -> str:
        return f"https://api.github.com/repos/{self.github_repo}/releases/tags"

    def build_opener(self):
        return build_opener(HTTPSHandler)

    def is_windows_platform(self, platform_name: str) -> bool:
        return platform_name.startswith("win")

    @classmethod
    def load(cls, root_path: Path | None = None) -> "BuildConfig":
        base_path = Path(root_path) if root_path is not None else Path(__file__).resolve().parents[2]
        return cls(root_path=base_path.resolve())


def build_config(root_path: Path) -> BuildConfig:
    return BuildConfig(root_path=root_path.resolve())
