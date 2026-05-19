from __future__ import annotations

import shutil
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Iterable

from scripts.build_tools.logging_utils import get_logger

logger = get_logger("archive")


class ArchiveExtractor:
    """
    Универсальный распаковщик архивов.

    Правила:
    - ZIP: распаковывается как есть.
    - TAR.GZ: если в корне одна общая папка-обёртка, она отбрасывается.
    """

    def __init__(self, archive_path: Path, dest_path: Path) -> None:
        self.archive_path = Path(archive_path).resolve()
        self.dest_path = Path(dest_path).resolve()

        if not self.archive_path.exists():
            raise FileNotFoundError(f"Архив не найден: {self.archive_path}")

        self.suffix = "".join(self.archive_path.suffixes).lower()

    def extract_all(self) -> None:
        logger.info("Extracting archive %s -> %s", self.archive_path, self.dest_path)
        if self.dest_path.exists():
            shutil.rmtree(self.dest_path, ignore_errors=True)
        self.dest_path.mkdir(parents=True, exist_ok=True)

        if self.suffix == ".zip":
            self._extract_zip()
        elif self.suffix == ".tar.gz":
            self._extract_tar_gz()
        else:
            raise ValueError(f"Unsupported archive format: {self.suffix}")

    def _extract_zip(self) -> None:
        with zipfile.ZipFile(self.archive_path) as archive:
            archive.extractall(path=self.dest_path)

    def _extract_tar_gz(self) -> None:
        with tarfile.open(self.archive_path, "r:*") as archive:
            members = archive.getmembers()
            if not members:
                logger.warning("Archive %s is empty", self.archive_path)
                return

            root_prefix = self._get_single_root_prefix(members)
            members_to_extract = self._trim_root_prefix(members, root_prefix) if root_prefix else members

            kwargs = {"path": str(self.dest_path), "members": members_to_extract}
            if sys.version_info >= (3, 12):
                kwargs["filter"] = "data"
            archive.extractall(**kwargs)

    def _trim_root_prefix(self, members: list[tarfile.TarInfo], root_prefix: str) -> list[tarfile.TarInfo]:
        processed: list[tarfile.TarInfo] = []
        prefix_len = len(root_prefix)
        for member in members:
            if member.name in {root_prefix, f"{root_prefix}/"}:
                continue
            if member.name.startswith(root_prefix):
                cloned = member.replace(deep=False)
                cloned.name = member.name[prefix_len:]
                if cloned.isdir() and not cloned.name.endswith("/"):
                    cloned.name += "/"
                processed.append(cloned)
        return processed

    @staticmethod
    def _get_single_root_prefix(members: Iterable[tarfile.TarInfo]) -> str:
        roots = {member.name.split("/")[0] for member in members if member.name}
        if len(roots) == 1:
            return f"{roots.pop()}/"
        return ""
