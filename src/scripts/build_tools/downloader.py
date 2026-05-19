from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request

from .config import BuildConfig
from .logging_utils import get_logger

logger = get_logger("downloader")


@dataclass(frozen=True)
class DownloadTask:
    url: str
    destination: Path


class FileDownloader:
    def __init__(self, config: BuildConfig) -> None:
        self._config = config
        self._opener = config.build_opener()
        self._lock = threading.Lock()

    def download(self, task: DownloadTask, retries: int = 3) -> Path:
        destination = task.destination
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            logger.info("Using cached archive: %s", destination)
            return destination

        temp_path = destination.with_suffix(destination.suffix + ".part")

        for attempt in range(1, retries + 1):
            initial_size = temp_path.stat().st_size if temp_path.exists() else 0
            try:
                downloaded_path = self._download_once(
                    task.url,
                    destination,
                    temp_path,
                    initial_size,
                )
                logger.info("Downloaded %s", downloaded_path)
                return downloaded_path
            except Exception as exc:
                logger.warning(
                    "Download attempt %s/%s failed for %s: %s",
                    attempt,
                    retries,
                    task.url,
                    exc,
                )
                if attempt == retries:
                    temp_path.unlink(missing_ok=True)
                    raise
        raise RuntimeError(f"Failed to download {task.url}")

    def _download_once(
        self,
        url: str,
        destination: Path,
        temp_path: Path,
        initial_size: int,
    ) -> Path:
        headers = {
            "Range": f"bytes={initial_size}-" if initial_size > 0 else "",
            "User-Agent": "pydajet-metadata-installer/1.0",
        }
        request = Request(url, headers=headers)
        with self._lock:
            response = self._opener.open(request, timeout=self._config.http_timeout)
        with response:
            status = getattr(response, "status", 200)
            if status == 416:
                temp_path.unlink(missing_ok=True)
                return self._download_once(url, destination, temp_path, 0)
            if status >= 400:
                body = response.read(200).decode(errors="replace")
                raise RuntimeError(f"HTTP {status}: {body}")

            write_mode = "ab" if initial_size > 0 else "wb"
            with open(temp_path, write_mode) as file_obj:
                shutil.copyfileobj(response, file_obj)

        temp_path.replace(destination)
        return destination
