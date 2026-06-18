from datetime import date

from psycopg import Connection


def upsert_category_pair(conn: Connection, lvl1: str, lvl2: str) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO categories (parent_id, name, level)
            VALUES (NULL, %s, 1)
            ON CONFLICT (parent_id, name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (lvl1,),
        )
        lvl1_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO categories (parent_id, name, level)
            VALUES (%s, %s, 2)
            ON CONFLICT (parent_id, name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (lvl1_id, lvl2),
        )
        lvl2_id = cur.fetchone()[0]
    return lvl1_id, lvl2_id


def upsert_keyword_group(conn: Connection, product_id: int, category_id: int, name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO keyword_groups (product_id, category_id, name)
            VALUES (%s, %s, %s)
            ON CONFLICT (product_id, name) DO UPDATE SET category_id = EXCLUDED.category_id
            RETURNING id
            """,
            (product_id, category_id, name),
        )
        return cur.fetchone()[0]


def upsert_round(
    conn: Connection,
    *,
    product_id: int,
    round_no: int,
    period_start: date,
    period_end: date,
    regular_bid_start: date | None = None,
    regular_bid_end: date | None = None,
    regular_announce_date: date | None = None,
    rebid_start: date | None = None,
    rebid_end: date | None = None,
    rebid_announce_date: date | None = None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO rounds (
                product_id, round_no, period_start, period_end,
                regular_bid_start, regular_bid_end, regular_announce_date,
                rebid_start, rebid_end, rebid_announce_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (product_id, round_no) DO UPDATE SET
                period_start = EXCLUDED.period_start,
                period_end = EXCLUDED.period_end,
                regular_bid_start = EXCLUDED.regular_bid_start,
                regular_bid_end = EXCLUDED.regular_bid_end,
                regular_announce_date = EXCLUDED.regular_announce_date,
                rebid_start = EXCLUDED.rebid_start,
                rebid_end = EXCLUDED.rebid_end,
                rebid_announce_date = EXCLUDED.rebid_announce_date
            RETURNING id
            """,
            (
                product_id,
                round_no,
                period_start,
                period_end,
                regular_bid_start,
                regular_bid_end,
                regular_announce_date,
                rebid_start,
                rebid_end,
                rebid_announce_date,
            ),
        )
        return cur.fetchone()[0]


def upsert_round_keyword_group(
    conn: Connection,
    *,
    round_id: int,
    keyword_group_id: int,
    reference_query_volume: int | None = None,
    min_bid_price: int | None = None,
    bid_status: str | None = None,
    empty_slots: int | None = None,
    keyword_count: int | None = None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO round_keyword_groups (
                round_id, keyword_group_id,
                reference_query_volume, min_bid_price, bid_status, empty_slots, keyword_count,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (round_id, keyword_group_id) DO UPDATE SET
                reference_query_volume = EXCLUDED.reference_query_volume,
                min_bid_price = EXCLUDED.min_bid_price,
                bid_status = EXCLUDED.bid_status,
                empty_slots = EXCLUDED.empty_slots,
                keyword_count = COALESCE(
                    EXCLUDED.keyword_count, round_keyword_groups.keyword_count
                ),
                updated_at = now()
            RETURNING id
            """,
            (
                round_id,
                keyword_group_id,
                reference_query_volume,
                min_bid_price,
                bid_status,
                empty_slots,
                keyword_count,
            ),
        )
        return cur.fetchone()[0]


def update_winning_bid(
    conn: Connection,
    *,
    round_keyword_group_id: int,
    winning_bid: int,
) -> None:
    """Set regular_winning_bid + captured_at for a round_keyword_group.

    Skips the update if the incoming `winning_bid` is below the existing
    min_bid_price — that indicates the value came from a re-auction (재입찰)
    rather than a regular-auction (정기입찰) winning bid, and per project
    convention only regular-auction winnings are tracked.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE round_keyword_groups
            SET regular_winning_bid = %s, captured_at = now(), updated_at = now()
            WHERE id = %s
              AND (min_bid_price IS NULL OR %s >= min_bid_price)
            """,
            (winning_bid, round_keyword_group_id, winning_bid),
        )


def start_ingest_run(
    conn: Connection,
    *,
    run_type: str,
    file_path: str | None = None,
    product_id: int | None = None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingest_runs (run_type, product_id, file_path, status)
            VALUES (%s, %s, %s, 'started')
            RETURNING id
            """,
            (run_type, product_id, file_path),
        )
        return cur.fetchone()[0]


def complete_ingest_run(
    conn: Connection,
    *,
    run_id: int,
    rows_total: int | None = None,
    rows_inserted: int | None = None,
    rows_updated: int | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_runs
            SET status = 'success',
                rows_total = %s,
                rows_inserted = %s,
                rows_updated = %s,
                completed_at = now()
            WHERE id = %s
            """,
            (rows_total, rows_inserted, rows_updated, run_id),
        )


def fail_ingest_run(conn: Connection, *, run_id: int, error_message: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_runs
            SET status = 'error', error_message = %s, completed_at = now()
            WHERE id = %s
            """,
            (error_message, run_id),
        )
