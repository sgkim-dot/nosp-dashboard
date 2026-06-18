"""JOB 3: scrape brands for currently-active rounds, populate round_brands."""

from __future__ import annotations

import argparse
import random
import sys
import time
from datetime import date

import httpx
from psycopg import Connection

from worker.db import connect
from worker.lib.brand_match import upsert_brand
from worker.lib.canonical_brand import (
    GENERIC_REDIRECT_HOSTS,
    normalize_host,
    platform_business_name,
)
from worker.lib.naver_search import close_pool, scrape_brands_with_detected_count
from worker.logging import configure_logging, get_logger
from worker.upsert import complete_ingest_run, fail_ingest_run, start_ingest_run

log = get_logger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# Base inter-keyword pause. Actual sleep is `_DELAY_SECONDS + uniform(0, _DELAY_JITTER)`
# so the request cadence isn't perfectly periodic (anti-bot signal).
_DELAY_SECONDS = 2.0
_DELAY_JITTER = 2.0


def fetch_business_name(url: str) -> str | None:
    """Stage 2: follow ader.naver.com redirect → return advertiser identifier.

    Returns ONE of:
      - normalized URL host (`direct.samsungfire.com`)
      - platform path identifier (`brand.naver.com/lactiv`)
      - None (couldn't resolve — upsert_brand falls back to __unverified__::)

    We INTENTIONALLY never extract Korean company names from HTML footers
    (e.g. `회사명: 주식회사 ABC`). Storing those in business_name confuses
    the brand-cleanup detector and creates duplicate rows for the same
    advertiser. Korean canonical names belong in `HOST_TO_BRAND`, keyed off
    the URL host returned here.
    """
    try:
        with httpx.Client(
            headers={"User-Agent": _USER_AGENT}, timeout=15.0, follow_redirects=True
        ) as client:
            resp = client.get(url)
            host = resp.url.host or None
            path = resp.url.path or ""
            # httpx returns query as bytes — decode for parse_qs compatibility
            raw_q = resp.url.query
            if isinstance(raw_q, bytes):
                query = raw_q.decode("utf-8", errors="replace")
            else:
                query = raw_q or ""
            if not host:
                return None
            # Priority 1: platform path-based identifier (brand.naver.com/X,
            # smartstore.naver.com/X, blog.naver.com/{blogId}).
            plat = platform_business_name(host, path, query)
            if plat:
                return plat
            # Priority 2: normalized URL host. See module docstring above —
            # never extract Korean company names from response HTML.
            norm = normalize_host(host)
            # Priority 3: generic redirect hosts (youtube.com, facebook.com,
            # tiktok.com, …) are never an advertiser identity. Return None
            # so upsert_brand falls back to display-side matching.
            if norm and norm in GENERIC_REDIRECT_HOSTS:
                return None
            return norm
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
        # COALESCE(search_keyword, name) — per-kg override for the Naver query
        # string. Display stays as `name`; only the scrape uses the override.
        # Example: SV 다이렉트인보험 searches Naver for "다이렉트보험".
        sql = """
            SELECT DISTINCT rkg.id,
                            COALESCE(kg.search_keyword, kg.name) AS scrape_keyword,
                            p.code,
                            p.max_brands_per_group
            FROM round_keyword_groups rkg
            JOIN rounds r ON r.id = rkg.round_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN products p ON p.id = r.product_id
            WHERE r.period_start <= %s AND r.period_end >= %s
        """
        params: tuple = (today, today)
        if skip_already_scraped:
            # Skip KGs scraped in the last 24h regardless of whether any ad
            # was found (brands_scraped_at is set even on 0-slot scrapes).
            sql += """
                AND (
                    rkg.brands_scraped_at IS NULL
                    OR rkg.brands_scraped_at < now() - interval '24 hours'
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
    detected_slot_count: int | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM round_brands WHERE round_keyword_group_id = %s",
            (rkg_id,),
        )
        # Always stamp brands_scraped_at — distinguishes "no advertiser running
        # at scrape time" (column set, 0 brand rows) from "not yet scraped"
        # (column NULL). detected_slot_count is also always written (may be 0)
        # so the dashboard can distinguish "page never rendered" (NULL) from
        # "page rendered, no ad" (0).
        cur.execute(
            """
            UPDATE round_keyword_groups
            SET brands_scraped_at = now(),
                detected_slot_count = %s
            WHERE id = %s
            """,
            (detected_slot_count, rkg_id),
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
                    round_keyword_group_id, brand_id, slot_no, display_name,
                    sub_title, description, source, confidence
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (round_keyword_group_id, slot_no)
                DO UPDATE SET
                    brand_id = EXCLUDED.brand_id,
                    display_name = EXCLUDED.display_name,
                    sub_title = EXCLUDED.sub_title,
                    description = EXCLUDED.description,
                    source = EXCLUDED.source,
                    confidence = EXCLUDED.confidence,
                    captured_at = now()
                """,
                (
                    rkg_id, brand_id, slot.slot_no, slot.display_name,
                    slot.sub_title, slot.description, source, confidence,
                ),
            )


def _persist_kg_brands(
    rkg_id: int,
    slots: list,
    business_names: dict[str | None, str | None],
    conn: Connection | None = None,
    detected_slot_count: int | None = None,
) -> None:
    """Persist brands for one keyword group.

    When `conn` is provided (test mode), writes participate in the caller's
    transaction. Otherwise opens a short-lived connection per kg so the Neon
    pooler doesn't drop a long-lived connection during multi-hour scrapes.
    """
    if conn is not None:
        _persist_kg_brands_impl(
            conn, rkg_id, slots, business_names, detected_slot_count
        )
        return
    with connect() as fresh:
        _persist_kg_brands_impl(
            fresh, rkg_id, slots, business_names, detected_slot_count
        )
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
                slots, detected_slot_count = scrape_brands_with_detected_count(
                    kw, product_code
                )
            except Exception:
                log.exception("scrape failed", keyword=kw)
                continue
            slots = [s for s in slots if s.product == product_code]

            # Resolve hosts first
            business_names: dict[str | None, str | None] = {}
            for s in slots:
                if s.destination_url and s.destination_url not in business_names:
                    business_names[s.destination_url] = fetch_business_name(s.destination_url)

            # Dedupe by host: Naver assigns different ad_ids to the same
            # advertiser across fetches (rotation), so a single 1-slot brand
            # can appear with N different ad_ids. Treat one host = one slot.
            seen_hosts: set[str] = set()
            unique_slots = []
            for s in slots:
                host = business_names.get(s.destination_url)
                key = host or f"_url::{s.destination_url}"
                if key in seen_hosts:
                    continue
                seen_hosts.add(key)
                unique_slots.append(s)
            slots = unique_slots[:max_brands]

            # Reassign slot_no to 1-based sequential after dedup
            slots = [s.model_copy(update={"slot_no": i + 1}) for i, s in enumerate(slots)]

            if not slots:
                log.info("no slots", keyword=kw, product=product_code)
                try:
                    _persist_kg_brands(
                        rkg_id, [], {}, conn=persist_conn,
                        detected_slot_count=detected_slot_count,
                    )
                except Exception:
                    log.exception("persist failed (no slots)", rkg_id=rkg_id)
                time.sleep(delay_seconds + random.uniform(0, _DELAY_JITTER))
                continue

            try:
                _persist_kg_brands(
                    rkg_id, slots, business_names, conn=persist_conn,
                    detected_slot_count=detected_slot_count,
                )
                slots_inserted += len(slots)
            except Exception:
                log.exception("persist failed", rkg_id=rkg_id, keyword=kw)

            time.sleep(delay_seconds + random.uniform(0, _DELAY_JITTER))

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

        close_pool()
        return {"slots_inserted": slots_inserted, "keyword_groups_scraped": kgs_scraped}
    except Exception as exc:
        close_pool()
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


def _cleanup_stale_runs(conn: Connection) -> None:
    """Mark any 'running' ingest_runs older than 1 hour as interrupted.

    These leftover rows come from previous runs that were force-killed (closing
    cmd window, machine sleep, etc.). Cleaning them keeps the ingest_runs table
    tidy and makes the dashboard's 'last run' indicator accurate.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_runs
            SET status = 'interrupted',
                error_message = COALESCE(error_message, 'process terminated; auto-cleanup on next start')
            WHERE run_type = 'brand_scrape'
              AND status = 'running'
              AND run_at < NOW() - INTERVAL '1 hour'
            """
        )
        if cur.rowcount > 0:
            log.info("cleaned up stale runs", count=cur.rowcount)
        conn.commit()


def _print_resume_status(conn: Connection) -> None:
    """Show how many active-round KGs are already done vs pending."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.code,
              COUNT(*) FILTER (WHERE rkg.brands_scraped_at IS NOT NULL
                               AND rkg.brands_scraped_at > NOW() - INTERVAL '24 hours') AS done,
              COUNT(*) AS total
            FROM round_keyword_groups rkg
            JOIN rounds r ON r.id = rkg.round_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN products p ON p.id = kg.product_id
            WHERE r.period_start <= CURRENT_DATE AND r.period_end >= CURRENT_DATE
            GROUP BY p.code
            ORDER BY p.code
            """
        )
        rows = cur.fetchall()
    if not rows:
        return
    print("=" * 60)
    print("  resume status (active rounds, last 24h)")
    print("=" * 60)
    grand_done = grand_total = 0
    for code, done, total in rows:
        pct = (100 * done // total) if total else 0
        print(f"  {code:<14}  {done:>5} / {total:<5} done  ({pct}%)")
        grand_done += done
        grand_total += total
    if grand_total:
        pct = 100 * grand_done // grand_total
        print(f"  {'TOTAL':<14}  {grand_done:>5} / {grand_total:<5} done  ({pct}%)")
    pending = grand_total - grand_done
    if pending:
        # ~20s per KG (mix of NP/SV) — rough back-of-envelope
        est_min = pending * 20 // 60
        print(f"  pending: {pending} KGs (~{est_min} min, give or take)")
    print("=" * 60)
    print()


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="cap on keyword groups (for pilot)")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip keyword groups scraped in the last 24 hours (safe to use every "
             "time — lets you stop+resume across machines/days)",
    )
    args = parser.parse_args(argv)

    with connect() as conn:
        _cleanup_stale_runs(conn)
        if args.resume:
            _print_resume_status(conn)
        result = scrape_brands_for_active_rounds(
            conn, limit=args.limit, skip_already_scraped=args.resume
        )
        log.info("brand scrape done", **result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
