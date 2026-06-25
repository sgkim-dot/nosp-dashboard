"""JOB 3: scrape brands for currently-active rounds, populate round_brands."""

from __future__ import annotations

import argparse
import os
import random
import sys
import threading
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
_DELAY_SECONDS = 0.8
_DELAY_JITTER = 0.7

# Watchdog: if no KG completes for this long, the process is presumed hung
# (Playwright deadlock, Chromium spawn freeze, etc.) and we force-exit so
# the BAT wrapper's retry loop can spawn a fresh Python process.
_WATCHDOG_SECONDS = 300  # 5 minutes
_last_progress_ts = time.time()

# Early-exit on consecutive scrape failures. Single failures are normal
# (rotation miss, transient driver crash); 10 in a row means Playwright is
# in a broken state and only a fresh process will recover.
_consecutive_scrape_failures = 0
_MAX_CONSECUTIVE_FAILURES = 10


# Process-wide cache for fetch_business_name. ader.naver.com redirect URLs
# are unique per (KG × ad placement) but the resolved smartstore product
# pages repeat across KGs. Caching avoids re-fetching the same URL within
# the same BAT cycle.
#
# NOTE: we ONLY cache successes. Caching failures used to compound a single
# transient timeout into 3 cycles worth of `__unverified__::` brand rows —
# once a URL was poisoned in cycle 1, it stayed poisoned through cycle 2/3.
# Letting failures re-try costs at most one extra fetch per cycle per URL.
_CACHE_MISS = object()
_BUSINESS_NAME_CACHE: dict[str, str] = {}


def _watchdog_thread() -> None:
    """Background watchdog. Force-exits the process if no progress for
    _WATCHDOG_SECONDS. os._exit bypasses Python locks so it works even
    if the main thread is deadlocked inside Playwright."""
    while True:
        time.sleep(30)
        elapsed = time.time() - _last_progress_ts
        if elapsed > _WATCHDOG_SECONDS:
            log.error(
                "watchdog: no progress, force-exiting for BAT retry",
                stuck_seconds=int(elapsed),
            )
            os._exit(2)


def _bump_progress() -> None:
    global _last_progress_ts
    _last_progress_ts = time.time()


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
    # Process-wide cache: same ader.naver.com redirect URL often appears
    # across multiple KGs in one BAT run (same ad seen in multiple keyword
    # groups). Successes only — see _BUSINESS_NAME_CACHE comment above.
    cached = _BUSINESS_NAME_CACHE.get(url)
    if cached is not None:
        return cached

    try:
        with httpx.Client(
            # Naver smartstore rate-limits aggressively but a healthy response
            # typically arrives in 2-4s. 5s was too tight — normal landings
            # timed out and poisoned the cache. 8s gives them room while still
            # capping a 429-storm at a manageable cost per URL.
            headers={"User-Agent": _USER_AGENT}, timeout=8.0, follow_redirects=True
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
                _BUSINESS_NAME_CACHE[url] = plat
                return plat
            # Priority 2: normalized URL host. See module docstring above —
            # never extract Korean company names from response HTML.
            norm = normalize_host(host)
            # Priority 3: generic redirect hosts (youtube.com, facebook.com,
            # tiktok.com, …) are never an advertiser identity. Return None
            # so upsert_brand falls back to display-side matching.
            if norm and norm in GENERIC_REDIRECT_HOSTS:
                return None
            if norm:
                _BUSINESS_NAME_CACHE[url] = norm
            return norm
    except Exception as e:
        # Don't dump full traceback for routine timeouts/429 — those are
        # expected when Naver rate-limits us. Log a short line instead.
        # NOTE: we deliberately do NOT cache the failure. A retry on the next
        # KG (or next cycle of the BAT) is cheaper than letting one transient
        # 429 spawn dozens of __unverified__:: brand rows that we'd have to
        # clean up later.
        log.warning("landing fetch failed", url=url[:120], err=type(e).__name__)
        return None


def _fetch_work_list(
    conn: Connection,
    *,
    limit: int | None,
    rkg_ids: list[int] | None,
    skip_already_scraped: bool,
    null_only: bool = False,
) -> list[tuple[int, str, str, int, int]]:
    # Round period_start / period_end are KST business days. Neon runs in UTC,
    # so `CURRENT_DATE` lags KST by up to 9 hours and the new Monday round
    # would not register as active until 09:00 KST. Cast NOW() to Asia/Seoul.
    with conn.cursor() as cur:
        sql = """
            SELECT DISTINCT rkg.id,
                            COALESCE(kg.search_keyword, kg.name) AS scrape_keyword,
                            p.code,
                            p.max_brands_per_group,
                            COALESCE(rkg.regular_winning_bid, 0) AS winning_bid
            FROM round_keyword_groups rkg
            JOIN rounds r ON r.id = rkg.round_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN products p ON p.id = r.product_id
            WHERE r.period_start <= (NOW() AT TIME ZONE 'Asia/Seoul')::date
              AND r.period_end   >= (NOW() AT TIME ZONE 'Asia/Seoul')::date
        """
        params: tuple = ()
        if null_only:
            # Only KGs that have never been scraped this round. Used in a
            # deadline sprint where the previous BAT already touched 24h-old
            # KGs and only the NULL set is critical.
            sql += " AND rkg.brands_scraped_at IS NULL"
        elif skip_already_scraped:
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
        # Process high-bid KGs first — they're the ones that matter most to
        # the operator. Wins two ways: (a) a half-finished BAT still has
        # captured the valuable KGs, (b) a force-rescrape spot-check is
        # less likely to come back saying "BAT hasn't reached it yet".
        sql += " ORDER BY winning_bid DESC, rkg.id"
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


def _process_one_kg(
    rkg_id: int,
    kw: str,
    product_code: str,
    max_brands: int,
    *,
    persist_conn: Connection | None,
    delay_seconds: float,
    winning_bid: int = 0,
) -> int:
    """Scrape + persist one keyword group. Returns slots_inserted for this kg.

    Returns 0 on scrape exception, 0 on no-slots, or len(slots) on success.
    Sleeps `delay_seconds + jitter` at the end either way.

    `winning_bid` is currently unused — bid-aware retry inside the main
    loop was disabled in favor of the 3-cycle BAT strategy (cycle 2/3
    re-scrape every active KG with --full, which is a cleaner way to
    catch the same misses without bloating cycle 1 wall-clock).
    """

    global _consecutive_scrape_failures
    try:
        slots, detected_slot_count = scrape_brands_with_detected_count(
            kw, product_code
        )
        _consecutive_scrape_failures = 0
    except Exception:
        _consecutive_scrape_failures += 1
        log.exception(
            "scrape failed", keyword=kw,
            consecutive=_consecutive_scrape_failures,
        )
        # Playwright's Chromium driver can die mid-run (memory pressure,
        # Windows Defender, idle socket close). Tear down so the next
        # call to _get_pool() spawns a fresh Chromium.
        try:
            close_pool()
        except Exception:
            log.exception("close_pool after scrape failure raised")
        _bump_progress()
        return 0
    slots = [s for s in slots if s.product == product_code]

    # Resolve hosts first
    business_names: dict[str | None, str | None] = {}
    for s in slots:
        if s.destination_url and s.destination_url not in business_names:
            business_names[s.destination_url] = fetch_business_name(s.destination_url)

    # Dedupe by host: Naver assigns different ad_ids to the same advertiser
    # across fetches (rotation), so a single 1-slot brand can appear with N
    # different ad_ids. Treat one host = one slot.
    seen_hosts: set[str] = set()
    unique_slots = []
    for s in slots:
        host = business_names.get(s.destination_url)
        key = host or f"_url::{s.destination_url}"
        if key in seen_hosts:
            continue
        seen_hosts.add(key)
        unique_slots.append(s)
    # The dot indicator on the ad carousel reports how many slots Naver is
    # actually rotating for this keyword. detected_slot_count IS that dot
    # count. If it's lower than max_brands_per_group, trust it — NOSP's
    # total_slots is the bid capacity, NOT the running advertiser count.
    # Without this cap a 1-slot KG that briefly rotated 2 different ad_ids
    # for the same advertiser ends up with two slot rows for the same brand.
    if detected_slot_count and detected_slot_count > 0:
        cap = min(max_brands, detected_slot_count)
    else:
        cap = max_brands
    slots = unique_slots[:cap]

    # Reassign slot_no to 1-based sequential after dedup
    slots = [s.model_copy(update={"slot_no": i + 1}) for i, s in enumerate(slots)]

    inserted = 0
    if not slots:
        log.info("no slots", keyword=kw, product=product_code)
        try:
            _persist_kg_brands(
                rkg_id, [], {}, conn=persist_conn,
                detected_slot_count=detected_slot_count,
            )
        except Exception:
            log.exception("persist failed (no slots)", rkg_id=rkg_id)
    else:
        try:
            _persist_kg_brands(
                rkg_id, slots, business_names, conn=persist_conn,
                detected_slot_count=detected_slot_count,
            )
            inserted = len(slots)
        except Exception:
            log.exception("persist failed", rkg_id=rkg_id, keyword=kw)

    time.sleep(delay_seconds + random.uniform(0, _DELAY_JITTER))
    _bump_progress()
    return inserted


def _find_real_miss_rkg_ids(conn: Connection) -> list[tuple[int, str, str, int, int]]:
    """Active KGs where the last scrape *saw* more slots than we *kept*.

    detected_slot_count > round_brands count → the page rendered more ad
    placements than ended up in our DB. The cheap fix: scrape them once more.
    Most of the time the second scrape captures the missing rotation.

    Caveat: detected_slot_count is ad_id-unique within a single fetch and
    can occasionally overshoot the NOSP slot capacity (e.g. multiple NP
    widgets on the same page, or an advertiser holding multiple SC ids).
    We cap the sweep to KGs whose detected count is plausible — within
    `total_slots` (which is the bid capacity NOSP reports). KGs with
    detected > total_slots are noise and skipped, otherwise the sweep
    keeps re-scraping the same impossible-to-match cases forever.

    Returns (rkg_id, keyword, product_code, max_brands) so callers can feed
    rows straight into `_process_one_kg`.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rkg.id,
                   COALESCE(kg.search_keyword, kg.name) AS scrape_keyword,
                   p.code,
                   p.max_brands_per_group,
                   COALESCE(rkg.regular_winning_bid, 0) AS winning_bid
            FROM round_keyword_groups rkg
            JOIN rounds r ON r.id = rkg.round_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN products p ON p.id = r.product_id
            WHERE r.period_start <= (NOW() AT TIME ZONE 'Asia/Seoul')::date
              AND r.period_end   >= (NOW() AT TIME ZONE 'Asia/Seoul')::date
              AND rkg.detected_slot_count IS NOT NULL
              AND rkg.detected_slot_count > (
                  SELECT COUNT(*)::int FROM round_brands rb
                  WHERE rb.round_keyword_group_id = rkg.id
              )
              AND rkg.detected_slot_count <= COALESCE(rkg.total_slots, 2)
            ORDER BY winning_bid DESC, rkg.id
            """
        )
        return cur.fetchall()


def scrape_brands_for_active_rounds(
    conn: Connection,
    *,
    limit: int | None = None,
    delay_seconds: float = _DELAY_SECONDS,
    rkg_ids: list[int] | None = None,
    skip_already_scraped: bool = False,
    null_only: bool = False,
    persist_conn: Connection | None = None,
    run_type: str = "brand_scrape",
) -> dict[str, int]:
    """Scrape brands for currently-active rounds.

    In production: uses a short-lived DB connection per keyword group so the
    Neon pooler doesn't drop us mid-scrape. The passed-in `conn` is used only
    for the initial work-list query and the ingest_runs lifecycle.

    In tests: pass `persist_conn=db_conn_fixture` so writes participate in the
    test's rolled-back transaction.
    """
    rows = _fetch_work_list(
        conn, limit=limit, rkg_ids=rkg_ids,
        skip_already_scraped=skip_already_scraped, null_only=null_only,
    )
    log.info("active keyword groups", count=len(rows))

    # Use a fresh connection for the ingest_run lifecycle so the INSERT
    # actually commits (the long-lived `conn` runs without autocommit and
    # we never commit it explicitly, so previously start rows were lost).
    if persist_conn is None:
        with connect() as ir_conn:
            run_id = start_ingest_run(ir_conn, run_type=run_type)
            ir_conn.commit()
    else:
        run_id = start_ingest_run(persist_conn, run_type=run_type)
    slots_inserted = 0
    kgs_scraped = 0
    sweep_kgs = 0

    try:
        for rkg_id, kw, product_code, max_brands, winning_bid in rows:
            kgs_scraped += 1
            slots_inserted += _process_one_kg(
                rkg_id, kw, product_code, max_brands,
                persist_conn=persist_conn, delay_seconds=delay_seconds,
                winning_bid=winning_bid,
            )
            if _consecutive_scrape_failures >= _MAX_CONSECUTIVE_FAILURES:
                log.error(
                    "too many consecutive scrape failures — exiting "
                    "for BAT retry",
                    consecutive=_consecutive_scrape_failures,
                )
                sys.exit(3)

        # Post-scrape real-miss sweep: any KG where detected > caught after
        # the main pass gets one more try. Catches NP rotation misses that
        # the first 8 fetches happened to skip. Skipped on targeted runs
        # (rkg_ids set) so a single-kg rescrape doesn't trigger a global sweep.
        #
        # Use a fresh connection — `conn` may have been dropped by the Neon
        # pooler over the multi-hour main loop. Wrap in try/except so a
        # sweep failure doesn't abort the whole cycle (worst case: no sweep
        # this run, but cycle 1 completes and the BAT proceeds to cycle 2).
        if rkg_ids is None:
            try:
                with connect() as sweep_conn:
                    sweep_rows = _find_real_miss_rkg_ids(sweep_conn)
                if sweep_rows:
                    log.info("post-scrape real-miss sweep", count=len(sweep_rows))
                    for s_rkg_id, s_kw, s_product, s_max, s_bid in sweep_rows:
                        sweep_kgs += 1
                        slots_inserted += _process_one_kg(
                            s_rkg_id, s_kw, s_product, s_max,
                            persist_conn=persist_conn, delay_seconds=delay_seconds,
                            winning_bid=s_bid,
                        )
                    log.info("post-scrape sweep done", swept=sweep_kgs)
            except Exception:
                log.exception("post-scrape sweep failed — skipping for this run")

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
        return {
            "slots_inserted": slots_inserted,
            "keyword_groups_scraped": kgs_scraped,
            "swept_real_misses": sweep_kgs,
        }
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


def _reset_dawn_zero_scrapes(conn: Connection) -> int:
    """NULL brands_scraped_at for active-NP KGs scraped in the dawn window
    (KST 03-09 = UTC 18-23) that came back 0-caught.

    Recall in that band is ~0% — almost certainly bot throttling. Re-queuing
    them at run start lets the new BAT pick them up at a fresh time-of-day.
    Run idempotently at the start of every brand_scrape: if no rows match
    it is a no-op.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE round_keyword_groups SET brands_scraped_at = NULL
            WHERE id IN (
                SELECT rkg.id
                FROM round_keyword_groups rkg
                JOIN rounds r ON r.id = rkg.round_id
                JOIN products p ON p.id = r.product_id
                WHERE p.code = 'NEW_PRODUCT'
                  AND r.period_start <= (NOW() AT TIME ZONE 'Asia/Seoul')::date AND r.period_end >= (NOW() AT TIME ZONE 'Asia/Seoul')::date
                  AND rkg.brands_scraped_at IS NOT NULL
                  AND EXTRACT(HOUR FROM rkg.brands_scraped_at AT TIME ZONE 'UTC') BETWEEN 18 AND 23
                  AND NOT EXISTS (
                      SELECT 1 FROM round_brands rb WHERE rb.round_keyword_group_id = rkg.id
                  )
            )
            """
        )
        reset_count = cur.rowcount
        conn.commit()
        if reset_count > 0:
            log.info("dawn-window 0-caught reset", count=reset_count)
        return reset_count


def _cleanup_stale_runs(conn: Connection) -> None:
    """Mark any stale 'started' ingest_runs older than 1 hour as interrupted.

    These leftover rows come from previous runs that were force-killed (closing
    cmd window, machine sleep, etc.). Cleaning them keeps the ingest_runs table
    tidy and makes the dashboard's 'last run' indicator accurate.

    Fix: previously matched status='running' (wrong — actual value is 'started')
    and run_type='brand_scrape' (wrong — new runs use 'brand_scrape:resume'
    etc.). Now matches both legacy and tagged run_types.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_runs
            SET status = 'interrupted',
                error_message = COALESCE(error_message, 'process terminated; auto-cleanup on next start')
            WHERE run_type LIKE 'brand_scrape%'
              AND status = 'started'
              AND run_at < NOW() - INTERVAL '1 hour'
            """
        )
        if cur.rowcount > 0:
            log.info("cleaned up stale runs", count=cur.rowcount)
        conn.commit()


def _print_progress_summary(
    conn: Connection, *, resume: bool, null_only: bool
) -> None:
    """Active-round KG distribution + recent throughput + ETA.

    Always printed at the start of every brand_scrape run so the operator
    can eyeball whether the BAT is starting from a sane state and how long
    it will take. Uses observed throughput from the last hour if available;
    otherwise falls back to a conservative 60s/KG.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.code,
              COUNT(*) AS total,
              COUNT(*) FILTER (WHERE rkg.brands_scraped_at IS NULL) AS null_cnt,
              COUNT(*) FILTER (WHERE rkg.brands_scraped_at > NOW() - INTERVAL '24 hours') AS done_24h,
              COUNT(*) FILTER (WHERE rkg.brands_scraped_at IS NOT NULL) AS ever
            FROM round_keyword_groups rkg
            JOIN rounds r ON r.id = rkg.round_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN products p ON p.id = kg.product_id
            WHERE r.period_start <= (NOW() AT TIME ZONE 'Asia/Seoul')::date
              AND r.period_end   >= (NOW() AT TIME ZONE 'Asia/Seoul')::date
            GROUP BY p.code
            ORDER BY p.code
            """
        )
        rows = cur.fetchall()
        cur.execute(
            "SELECT COUNT(*) FROM round_keyword_groups "
            "WHERE brands_scraped_at > NOW() - INTERVAL '60 minutes'"
        )
        last60_count = cur.fetchone()[0] or 0
    if not rows:
        print("(no active rounds — was the weekly NOSP update ingested?)")
        return

    mode = (
        "NULL-only" if null_only
        else "resume (24h skip)" if resume
        else "full (re-scrape all active)"
    )

    print("=" * 64)
    print(f"  brand_scrape start — mode: {mode}")
    print("=" * 64)

    pending_total = 0
    for code, total, null_cnt, done_24h, ever in rows:
        if null_only:
            pending = null_cnt
        elif resume:
            pending = total - done_24h
        else:
            pending = total
        pending_total += pending
        ever_pct = (100 * ever // total) if total else 0
        d24_pct = (100 * done_24h // total) if total else 0
        print(
            f"  {code:<14}  total={total:<5} ever={ever:>4} ({ever_pct}%)  "
            f"24h={done_24h:>4} ({d24_pct}%)  NULL={null_cnt:<4}  →  pending={pending}"
        )

    # ETA from observed throughput, fallback to 60s.
    if last60_count >= 10:
        sec_per_kg = 3600 / last60_count
        src = f"last-1h pace = {sec_per_kg:.0f}s/KG"
    else:
        sec_per_kg = 60.0
        src = f"fallback (last-1h={last60_count} insufficient) — 60s/KG"

    eta_hr = (pending_total * sec_per_kg) / 3600
    print()
    print(f"  pending: {pending_total} KGs  |  {src}")
    print(f"  ETA: ~{eta_hr:.1f} hours")
    print("=" * 64)
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
    parser.add_argument(
        "--null-only",
        action="store_true",
        dest="null_only",
        help="only process KGs with brands_scraped_at IS NULL — used for "
             "deadline sprints where the rest of the round is already covered.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="ignore the 24h skip and re-scrape every active KG. Used in the "
             "2nd/3rd cycle of the multi-pass BAT to converge missed advertisers.",
    )
    args = parser.parse_args(argv)

    # --full overrides --resume (and --null-only) — re-scrape every active KG.
    use_resume = args.resume and not args.full
    use_null_only = args.null_only and not args.full

    # Watchdog: detect Python deadlock (Playwright spawn freezes,
    # connection-close hangs) and force-exit so the BAT can retry.
    threading.Thread(target=_watchdog_thread, daemon=True).start()
    _bump_progress()

    # Tag ingest_runs with the cycle mode so the dashboard can render
    # "cycle 1 (resume) / cycle 2 (full) / cycle 3 (full)" separately.
    if args.full:
        run_type = "brand_scrape:full"
    elif use_null_only:
        run_type = "brand_scrape:null-only"
    elif use_resume:
        run_type = "brand_scrape:resume"
    else:
        run_type = "brand_scrape"

    with connect() as conn:
        _cleanup_stale_runs(conn)
        _reset_dawn_zero_scrapes(conn)
        _print_progress_summary(conn, resume=use_resume, null_only=use_null_only)
        result = scrape_brands_for_active_rounds(
            conn, limit=args.limit,
            skip_already_scraped=use_resume, null_only=use_null_only,
            run_type=run_type,
        )
        log.info("brand scrape done", run_type=run_type, **result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
