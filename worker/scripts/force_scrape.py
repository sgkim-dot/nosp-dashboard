"""Manually scrape + persist a few high-visibility KGs so the user can see data
on the dashboard while the background scraper catches up."""
from worker.db import connect
from worker.lib.naver_search import scrape_brands_for_keyword
from worker.jobs.brand_scrape import fetch_business_name, _persist_kg_brands

# (keyword, product_code) — pairs to force-scrape
TARGETS = [
    ("운전자보험", "SEARCHING_VIEW"),
    ("운전자보험", "NEW_PRODUCT"),
    ("간병치매보험", "SEARCHING_VIEW"),
    ("간병치매보험", "NEW_PRODUCT"),
    ("실비보험", "SEARCHING_VIEW"),
    ("실비보험", "NEW_PRODUCT"),
    ("자동차보험", "SEARCHING_VIEW"),
    ("자동차보험", "NEW_PRODUCT"),
    ("암보험", "SEARCHING_VIEW"),
    ("암보험", "NEW_PRODUCT"),
]

def find_active_rkg(conn, kw: str, product_code: str) -> tuple[int, int] | None:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT rkg.id, p.max_brands_per_group
            FROM round_keyword_groups rkg
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN rounds r ON r.id = rkg.round_id
            JOIN products p ON p.id = r.product_id
            WHERE kg.name = %s AND p.code = %s
              AND CURRENT_DATE BETWEEN r.period_start AND r.period_end
            LIMIT 1
        """, (kw, product_code))
        row = cur.fetchone()
        return (row[0], row[1]) if row else None


with connect() as conn:
    for kw, prod in TARGETS:
        info = find_active_rkg(conn, kw, prod)
        if not info:
            print(f"[skip] {kw} ({prod}) — no active RKG")
            continue
        rkg_id, max_brands = info
        try:
            raw_slots = scrape_brands_for_keyword(kw, prod)
        except Exception as e:
            print(f"[err] {kw} ({prod}): {e}")
            continue
        slots = [s for s in raw_slots if s.product == prod][:max_brands]

        business_names = {}
        for s in slots:
            if s.destination_url and s.destination_url not in business_names:
                business_names[s.destination_url] = fetch_business_name(s.destination_url)

        try:
            _persist_kg_brands(rkg_id, slots, business_names, conn=conn)
            conn.commit()
            if slots:
                names = ", ".join(f"{s.display_name[:30]} ({business_names.get(s.destination_url)})" for s in slots)
                print(f"[ok] {kw} ({prod}): {len(slots)} slots → {names}")
            else:
                print(f"[ok] {kw} ({prod}): 0 slots (no ads currently running)")
        except Exception as e:
            print(f"[persist err] {kw} ({prod}): {e}")
            conn.rollback()
