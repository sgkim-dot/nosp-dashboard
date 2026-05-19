"""High-level CSV -> DB orchestrator (JOB 2)."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re

from psycopg import Connection

from worker.csv_parsers import parse_bid_info_csv, parse_winning_bid_csv
from worker.logging import get_logger
from worker.models import BidInfoRow, WinningBidRow
from worker.upsert import (
    complete_ingest_run,
    fail_ingest_run,
    start_ingest_run,
    update_winning_bid,
    upsert_category_pair,
    upsert_keyword_group,
    upsert_round,
    upsert_round_keyword_group,
)

log = get_logger(__name__)

_QUERY_DATE = re.compile(r"조회일자\s*[:：]\s*(\d{8})")


@dataclass
class IngestResult:
    rows_total: int
    rows_inserted: int
    rows_updated: int
    run_id: int


def _read_query_date(path: Path) -> date:
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            m = _QUERY_DATE.search(line)
            if m:
                s = m.group(1)
                return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    raise ValueError(f"조회일자 not found in {path}")


def _product_id(conn: Connection, code: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM products WHERE code = %s", (code,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"product not found: {code}")
        return row[0]


def ingest_csv(
    conn: Connection,
    *,
    path: Path,
    product_code: str,
    kind: str,
) -> IngestResult:
    run_type = "csv_bid_info" if kind == "bid_info" else "csv_winning"
    product_id = _product_id(conn, product_code)
    run_id = start_ingest_run(
        conn, run_type=run_type, file_path=str(path), product_id=product_id
    )

    try:
        if kind == "bid_info":
            result = _ingest_bid_info(conn, path, product_id, run_id)
        elif kind == "winning":
            result = _ingest_winning(conn, path, product_id, run_id)
        else:
            raise ValueError(f"unknown kind: {kind}")
        complete_ingest_run(
            conn,
            run_id=run_id,
            rows_total=result.rows_total,
            rows_inserted=result.rows_inserted,
            rows_updated=result.rows_updated,
        )
        return result
    except Exception as exc:
        fail_ingest_run(conn, run_id=run_id, error_message=str(exc))
        raise


def _row_exists_for(conn: Connection, product_id: int, row: BidInfoRow) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM round_keyword_groups rkg
            JOIN rounds r  ON r.id  = rkg.round_id  AND r.product_id  = %s AND r.round_no = %s
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id AND kg.product_id = %s AND kg.name = %s
            LIMIT 1
            """,
            (product_id, row.round_no, product_id, row.keyword_group),
        )
        return cur.fetchone() is not None


def _load_existing_rkg_keys(conn: Connection, product_id: int) -> set[tuple[int, str]]:
    """Pre-load (round_no, kg_name) for all existing round_keyword_groups of this product."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.round_no, kg.name
            FROM round_keyword_groups rkg
            JOIN rounds r ON r.id = rkg.round_id AND r.product_id = %s
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id AND kg.product_id = %s
            """,
            (product_id, product_id),
        )
        return {(rn, nm) for rn, nm in cur.fetchall()}


def _ingest_bid_info(
    conn: Connection, path: Path, product_id: int, run_id: int
) -> IngestResult:
    # Parse all rows into memory first
    rows = list(parse_bid_info_csv(path))

    # Pre-load existing RKG keys to avoid per-row existence checks (single query)
    existing_keys: set[tuple[int, str]] = _load_existing_rkg_keys(conn, product_id)

    # In-memory caches to avoid repeated identical DB round-trips
    category_pair_cache: dict[tuple[str, str], tuple[int, int]] = {}
    kg_cache: dict[tuple[int, str], int] = {}  # (product_id, name) -> id
    round_cache: dict[int, int] = {}  # round_no -> id

    # Phase 1: upsert all unique category pairs (deduplicated)
    for row in rows:
        cat_key = (row.category_lvl1, row.category_lvl2)
        if cat_key not in category_pair_cache:
            category_pair_cache[cat_key] = upsert_category_pair(conn, row.category_lvl1, row.category_lvl2)

    # Phase 2: upsert all unique keyword groups (deduplicated)
    for row in rows:
        kg_key = (product_id, row.keyword_group)
        if kg_key not in kg_cache:
            _, lvl2_id = category_pair_cache[(row.category_lvl1, row.category_lvl2)]
            kg_cache[kg_key] = upsert_keyword_group(conn, product_id, lvl2_id, row.keyword_group)

    # Phase 3: upsert all unique rounds (deduplicated)
    for row in rows:
        if row.round_no not in round_cache:
            round_cache[row.round_no] = upsert_round(
                conn,
                product_id=product_id,
                round_no=row.round_no,
                period_start=row.period_start,
                period_end=row.period_end,
                regular_bid_start=row.regular_bid_start,
                regular_bid_end=row.regular_bid_end,
                regular_announce_date=row.regular_announce_date,
                rebid_start=row.rebid_start,
                rebid_end=row.rebid_end,
                rebid_announce_date=row.rebid_announce_date,
            )

    # Phase 4: upsert all round_keyword_groups (one per row - unavoidable)
    # Use executemany-style bulk insert for better performance
    total = inserted = updated = 0
    rkg_params = []
    for row in rows:
        round_id = round_cache[row.round_no]
        kg_id = kg_cache[(product_id, row.keyword_group)]
        rkg_params.append((
            round_id, kg_id,
            row.reference_query_volume, row.min_bid_price,
            row.bid_status, row.empty_slots,
        ))
        total += 1
        if (row.round_no, row.keyword_group) in existing_keys:
            updated += 1
        else:
            inserted += 1

    # Bulk upsert round_keyword_groups using executemany
    if rkg_params:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO round_keyword_groups (
                    round_id, keyword_group_id,
                    reference_query_volume, min_bid_price, bid_status, empty_slots,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (round_id, keyword_group_id) DO UPDATE SET
                    reference_query_volume = EXCLUDED.reference_query_volume,
                    min_bid_price = EXCLUDED.min_bid_price,
                    bid_status = EXCLUDED.bid_status,
                    empty_slots = EXCLUDED.empty_slots,
                    updated_at = now()
                """,
                rkg_params,
            )

    log.info("bid_info ingested", total=total, inserted=inserted, updated=updated)
    return IngestResult(total, inserted, updated, run_id)


def _ingest_winning(
    conn: Connection, path: Path, product_id: int, run_id: int
) -> IngestResult:
    query_date = _read_query_date(path)
    total = updated = 0
    for w_row in parse_winning_bid_csv(path):
        rkg_id = _latest_announced_rkg(conn, product_id, w_row, query_date)
        if rkg_id is None:
            log.warning(
                "no round to attach winning bid",
                product_id=product_id,
                keyword_group=w_row.keyword_group,
            )
            continue
        update_winning_bid(conn, round_keyword_group_id=rkg_id, winning_bid=w_row.recent_winning_bid)
        total += 1
        updated += 1
    return IngestResult(total, 0, updated, run_id)


def _latest_announced_rkg(
    conn: Connection, product_id: int, w_row: WinningBidRow, query_date: date
) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rkg.id
            FROM round_keyword_groups rkg
            JOIN rounds r  ON r.id  = rkg.round_id  AND r.product_id  = %s
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id AND kg.product_id = %s AND kg.name = %s
            WHERE r.regular_announce_date IS NOT NULL
              AND r.regular_announce_date <= %s
            ORDER BY r.regular_announce_date DESC
            LIMIT 1
            """,
            (product_id, product_id, w_row.keyword_group, query_date),
        )
        row = cur.fetchone()
        return row[0] if row else None
