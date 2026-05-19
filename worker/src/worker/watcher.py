"""Inbox/ folder watcher (manual drop fallback — path A of B->C->A cascade)."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from worker.logging import get_logger

log = get_logger(__name__)

_KNOWN_PREFIXES = ("서칭뷰_", "신제품_")
_RAW_ROOT = Path("raw")


def _looks_like_nosp_csv(name: str) -> bool:
    return name.lower().endswith(".csv") and name.startswith(_KNOWN_PREFIXES)


def _archive(path: Path) -> Path:
    today = date.today().isoformat()
    dest_dir = _RAW_ROOT / today
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    shutil.move(str(path), str(dest))
    return dest


class _IngestHandler(FileSystemEventHandler):
    def __init__(self, ingest_fn: Callable[[Path], None]) -> None:
        self._ingest = ingest_fn

    def on_created(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        self._handle(event.src_path)

    def on_moved(self, event):  # type: ignore[override]
        if event.is_directory:
            return
        self._handle(event.dest_path)

    def _handle(self, src_path: str) -> None:
        path = Path(src_path)
        if not _looks_like_nosp_csv(path.name):
            return
        time.sleep(0.5)
        archived = _archive(path)
        try:
            self._ingest(archived)
        except Exception:
            log.exception("ingest failed", file=str(archived))


def watch_inbox(inbox: Path) -> None:
    inbox.mkdir(parents=True, exist_ok=True)
    from worker.jobs.csv_ingest import ingest_one

    handler = _IngestHandler(ingest_fn=ingest_one)
    observer = Observer()
    observer.schedule(handler, str(inbox), recursive=False)
    observer.start()
    log.info("watching inbox", path=str(inbox))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
