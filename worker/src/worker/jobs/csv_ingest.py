"""JOB 2: CSV ingest.

Usage:
    uv run python -m worker.jobs.csv_ingest --file path/to/file.csv \
        --product SEARCHING_VIEW --kind bid_info
    uv run python -m worker.jobs.csv_ingest --watch  # watches inbox/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from worker.db import connect
from worker.ingest import ingest_csv
from worker.logging import configure_logging, get_logger

log = get_logger(__name__)


def _detect_kind_and_product(name: str) -> tuple[str, str]:
    """Infer (product_code, kind) from the NOSP filename pattern."""
    n = name
    product = (
        "SEARCHING_VIEW"
        if n.startswith("서칭뷰_")
        else "NEW_PRODUCT"
        if n.startswith("신제품_")
        else None
    )
    kind = (
        "bid_info"
        if "회차별입찰정보" in n
        else "winning"
        if "키워드그룹별최근낙찰가" in n
        else None
    )
    if product is None or kind is None:
        raise ValueError(f"could not classify file: {name}")
    return product, kind


def ingest_one(path: Path, product: str | None = None, kind: str | None = None) -> None:
    if product is None or kind is None:
        product, kind = _detect_kind_and_product(path.name)
    with connect() as conn:
        result = ingest_csv(conn, path=path, product_code=product, kind=kind)
        conn.commit()
        log.info(
            "ingest done",
            file=str(path),
            product=product,
            kind=kind,
            total=result.rows_total,
            inserted=result.rows_inserted,
            updated=result.rows_updated,
        )


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, help="single CSV to ingest")
    parser.add_argument("--product", choices=["SEARCHING_VIEW", "NEW_PRODUCT"])
    parser.add_argument("--kind", choices=["bid_info", "winning"])
    parser.add_argument("--watch", action="store_true", help="watch inbox/ folder")
    parser.add_argument(
        "--backfill",
        type=Path,
        metavar="DIR",
        help="batch-ingest all NOSP CSVs in DIR in safe order",
    )
    args = parser.parse_args(argv)

    if args.backfill:
        from worker.backfill import backfill_directory

        backfill_directory(args.backfill)
        return 0

    if args.watch:
        from worker.watcher import watch_inbox

        watch_inbox(Path("inbox"))
        return 0

    if not args.file:
        parser.error("--file is required when not --watch")

    ingest_one(args.file, args.product, args.kind)
    return 0


if __name__ == "__main__":
    sys.exit(main())
