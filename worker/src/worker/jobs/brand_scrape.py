"""JOB 3: scrape brands for currently-active rounds, populate round_brands."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date

import httpx
from psycopg import Connection

from worker.db import connect
from worker.lib.brand_match import upsert_brand
from worker.lib.landing import extract_business_name
from worker.lib.naver_search import scrape_brands_for_keyword
from worker.logging import configure_logging, get_logger
from worker.upsert import complete_ingest_run, fail_ingest_run, start_ingest_run

log = get_logger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_DELAY_SECONDS = 3.0


def fetch_business_name(url: str) -> str | None:
    """Stage 2: GET the landing URL (following redirects), extract 사업자등록상호."""
    try:
        with httpx.Client(
            headers={"User-Agent": _USER_AGENT}, timeout=20.0, follow_redirects=True
        ) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return None
            return extract_business_name(resp.text)
    except Exception:
        log.exception("landing fetch failed", url=url)
        return None


def scrape_brands_for_active_rounds(
    conn: Connection,
    *,
    limit: int | None = None,
    delay_seconds: float = _DELAY_SECONDS,
    rkg_ids: list[int] | None = None,
) -> dict[str, int]:
    today = date.today().isoformat()
    run_id = start_ingest_run(conn, run_type="brand_scrape")
    slots_inserted = 0
    kgs_scraped = 0

    try:
        with conn.cursor() as cur:
            sql = """
                SELECT DISTINCT rkg.id, kg.name, p.code, p.max_brands_per_group
                FROM round_keyword_groups rkg
                JOIN rounds r ON r.id = rkg.round_id
                JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
                JOIN products p ON p.id = r.product_id
                WHERE r.period_start <= %s AND r.period_end >= %s
            """
            params: tuple = (today, today)
            if rkg_ids is not None:
                sql += " AND rkg.id = ANY(%s)"
                params = (*params, rkg_ids)
            if limit:
                sql += " LIMIT %s"
                params = (*params, limit)
            cur.execute(sql, params)
            rows = cur.fetchall()

        log.info("active keyword groups", count=len(rows))

        for rkg_id, kw, product_code, max_brands in rows:
            kgs_scraped += 1
            try:
                slots = scrape_brands_for_keyword(kw)
            except Exception:
                log.exception("scrape failed", keyword=kw)
                continue
            slots = [s for s in slots if s.product == product_code][:max_brands]

            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM round_brands WHERE round_keyword_group_id = %s",
                    (rkg_id,),
                )

            if not slots:
                log.info("no slots", keyword=kw, product=product_code)
                time.sleep(delay_seconds)
                continue

            for slot in slots:
                business_name = (
                    fetch_business_name(slot.destination_url) if slot.destination_url else None
                )
                confidence = 0.95 if business_name else 0.75
                source = "landing" if business_name else "dom"
                brand_id = upsert_brand(
                    conn,
                    business_name=business_name,
                    display_name=slot.display_name,
                )
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO round_brands (
                            round_keyword_group_id, brand_id, slot_no, source, confidence
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (round_keyword_group_id, slot_no)
                        DO UPDATE SET
                            brand_id = EXCLUDED.brand_id,
                            source = EXCLUDED.source,
                            confidence = EXCLUDED.confidence,
                            captured_at = now()
                        """,
                        (rkg_id, brand_id, slot.slot_no, source, confidence),
                    )
                slots_inserted += 1

            time.sleep(delay_seconds)

        complete_ingest_run(
            conn,
            run_id=run_id,
            rows_total=kgs_scraped,
            rows_inserted=slots_inserted,
        )
        return {"slots_inserted": slots_inserted, "keyword_groups_scraped": kgs_scraped}
    except Exception as exc:
        fail_ingest_run(conn, run_id=run_id, error_message=str(exc))
        raise


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="cap on keyword groups (for pilot)")
    args = parser.parse_args(argv)

    with connect() as conn:
        result = scrape_brands_for_active_rounds(conn, limit=args.limit)
        conn.commit()
        log.info("brand scrape done", **result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
