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
    """Stage 2: follow ader.naver.com redirect → return final landing hostname.

    Modern advertiser landing pages are SPAs, so 사업자등록상호 text isn't in the
    raw HTML. Instead we use the final URL's hostname (after redirects) as a
    canonical advertiser identifier (e.g. "direct.samsungfire.com",
    "jacomo.co.kr"). Same advertiser → same hostname → unique brand.

    The 사업자등록상호 regex fallback is still attempted in case the page does
    have a server-rendered footer.
    """
    try:
        with httpx.Client(
            headers={"User-Agent": _USER_AGENT}, timeout=15.0, follow_redirects=True
        ) as client:
            resp = client.get(url)
            host = resp.url.host or None
            if host:
                # Try regex fallback first (more informative if it works)
                if resp.status_code == 200:
                    biz = extract_business_name(resp.text)
                    if biz:
                        return biz
                # Otherwise use the hostname as the canonical identifier
                return host
            return None
    except Exception:
        log.exception("landing fetch failed", url=url)
        return None


def _fetch_work_list(
    conn: Connection,
    *,
    limit: int | None,
    rkg_ids: list[int] | None,
    skip_already_scraped: bool,
) -> list[tuple[int, str, str, int]]:
    today = date.today().isoformat()
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
        if skip_already_scraped:
            sql += """
                AND NOT EXISTS (
                    SELECT 1 FROM round_brands rb
                    WHERE rb.round_keyword_group_id = rkg.id
                      AND rb.captured_at >= now() - interval '24 hours'
                )
            """
        if rkg_ids is not None:
            sql += " AND rkg.id = ANY(%s)"
            params = (*params, rkg_ids)
        if limit:
            sql += " LIMIT %s"
            params = (*params, limit)
        cur.execute(sql, params)
        return cur.fetchall()


def _persist_kg_brands_impl(
    conn: Connection,
    rkg_id: int,
    slots: list,
    business_names: dict[str | None, str | None],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM round_brands WHERE round_keyword_group_id = %s",
            (rkg_id,),
        )
    for slot in slots:
        business_name = business_names.get(slot.destination_url)
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


def _persist_kg_brands(
    rkg_id: int,
    slots: list,
    business_names: dict[str | None, str | None],
    conn: Connection | None = None,
) -> None:
    """Persist brands for one keyword group.

    When `conn` is provided (test mode), writes participate in the caller's
    transaction. Otherwise opens a short-lived connection per kg so the Neon
    pooler doesn't drop a long-lived connection during multi-hour scrapes.
    """
    if conn is not None:
        _persist_kg_brands_impl(conn, rkg_id, slots, business_names)
        return
    with connect() as fresh:
        _persist_kg_brands_impl(fresh, rkg_id, slots, business_names)
        fresh.commit()


def scrape_brands_for_active_rounds(
    conn: Connection,
    *,
    limit: int | None = None,
    delay_seconds: float = _DELAY_SECONDS,
    rkg_ids: list[int] | None = None,
    skip_already_scraped: bool = False,
    persist_conn: Connection | None = None,
) -> dict[str, int]:
    """Scrape brands for currently-active rounds.

    In production: uses a short-lived DB connection per keyword group so the
    Neon pooler doesn't drop us mid-scrape. The passed-in `conn` is used only
    for the initial work-list query and the ingest_runs lifecycle.

    In tests: pass `persist_conn=db_conn_fixture` so writes participate in the
    test's rolled-back transaction.
    """
    rows = _fetch_work_list(
        conn, limit=limit, rkg_ids=rkg_ids, skip_already_scraped=skip_already_scraped
    )
    log.info("active keyword groups", count=len(rows))

    run_id = start_ingest_run(conn, run_type="brand_scrape")
    slots_inserted = 0
    kgs_scraped = 0

    try:
        for rkg_id, kw, product_code, max_brands in rows:
            kgs_scraped += 1
            try:
                slots = scrape_brands_for_keyword(kw, product_code)
            except Exception:
                log.exception("scrape failed", keyword=kw)
                continue
            slots = [s for s in slots if s.product == product_code][:max_brands]

            if not slots:
                log.info("no slots", keyword=kw, product=product_code)
                try:
                    _persist_kg_brands(rkg_id, [], {}, conn=persist_conn)
                except Exception:
                    log.exception("persist failed (no slots)", rkg_id=rkg_id)
                time.sleep(delay_seconds)
                continue

            business_names: dict[str | None, str | None] = {}
            for s in slots:
                if s.destination_url and s.destination_url not in business_names:
                    business_names[s.destination_url] = fetch_business_name(s.destination_url)

            try:
                _persist_kg_brands(rkg_id, slots, business_names, conn=persist_conn)
                slots_inserted += len(slots)
            except Exception:
                log.exception("persist failed", rkg_id=rkg_id, keyword=kw)

            time.sleep(delay_seconds)

        # In production, reopen for the final ingest_runs update so the
        # original `conn` may have been killed by the pooler by now.
        if persist_conn is None:
            try:
                with connect() as fresh:
                    complete_ingest_run(
                        fresh,
                        run_id=run_id,
                        rows_total=kgs_scraped,
                        rows_inserted=slots_inserted,
                    )
                    fresh.commit()
            except Exception:
                log.exception("complete_ingest_run failed", run_id=run_id)
        else:
            complete_ingest_run(
                persist_conn,
                run_id=run_id,
                rows_total=kgs_scraped,
                rows_inserted=slots_inserted,
            )

        return {"slots_inserted": slots_inserted, "keyword_groups_scraped": kgs_scraped}
    except Exception as exc:
        if persist_conn is None:
            try:
                with connect() as fresh:
                    fail_ingest_run(fresh, run_id=run_id, error_message=str(exc))
                    fresh.commit()
            except Exception:
                log.exception("fail_ingest_run failed", run_id=run_id)
        else:
            fail_ingest_run(persist_conn, run_id=run_id, error_message=str(exc))
        raise


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="cap on keyword groups (for pilot)")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip keyword groups scraped in the last 24 hours",
    )
    args = parser.parse_args(argv)

    with connect() as conn:
        result = scrape_brands_for_active_rounds(
            conn, limit=args.limit, skip_already_scraped=args.resume
        )
        log.info("brand scrape done", **result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
