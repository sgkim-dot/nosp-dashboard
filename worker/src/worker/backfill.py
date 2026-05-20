"""Directory walker + safe-order driver for batch CSV ingest (JOB 2 backfill)."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from worker.jobs.csv_ingest import _detect_kind_and_product, ingest_one
from worker.logging import get_logger

log = get_logger(__name__)

_NUM_TAIL = re.compile(r" \((\d+)\)(?=\.[^.]+$)")
_RAW_ROOT = Path("raw")


@dataclass(frozen=True)
class ClassifiedFile:
    path: Path
    product: str
    kind: str


@dataclass
class BackfillResult:
    success: int = 0
    error: int = 0
    skipped: int = 0


def _natural_key(path: Path) -> tuple[int, str]:
    m = _NUM_TAIL.search(path.name)
    n = int(m.group(1)) if m else 0
    return (n, path.name)


def classify_and_sort(directory: Path) -> list[ClassifiedFile]:
    out: list[ClassifiedFile] = []
    for p in sorted(directory.iterdir()):
        if not p.is_file() or p.suffix.lower() != ".csv":
            continue
        try:
            product, kind = _detect_kind_and_product(p.name)
        except ValueError:
            log.warning("skipping unrecognized file", file=p.name)
            continue
        out.append(ClassifiedFile(path=p, product=product, kind=kind))

    kind_rank = {"bid_info": 0, "winning": 1}
    return sorted(
        out,
        key=lambda cf: (kind_rank[cf.kind], cf.product, _natural_key(cf.path)),
    )


def _archive(path: Path) -> Path:
    """Move `path` into `raw/<today>/`. Tolerates Windows shutil quirks where
    the file ends up at the destination but shutil.move raises an exception."""
    today = date.today().isoformat()
    dest_dir = _RAW_ROOT / today
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    try:
        shutil.move(str(path), str(dest))
    except (FileNotFoundError, OSError):
        # Windows + shutil.move sometimes raises after successfully moving the
        # file. Treat as success iff dest exists and src no longer does.
        if dest.exists() and not path.exists():
            log.warning("archive raised but file moved; tolerating", file=path.name)
        else:
            raise
    return dest


def backfill_directory(directory: Path, *, archive: bool = True) -> BackfillResult:
    result = BackfillResult()
    classified = classify_and_sort(directory)

    all_csvs = sum(1 for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".csv")
    result.skipped = all_csvs - len(classified)

    log.info(
        "backfill starting",
        directory=str(directory),
        total=len(classified),
        skipped=result.skipped,
    )

    for cf in classified:
        try:
            ingest_one(cf.path, product=cf.product, kind=cf.kind)
            if archive:
                _archive(cf.path)
            result.success += 1
        except Exception as exc:
            log.exception("backfill file failed", file=cf.path.name, error=str(exc))
            result.error += 1

    log.info(
        "backfill done",
        success=result.success,
        error=result.error,
        skipped=result.skipped,
    )
    return result
