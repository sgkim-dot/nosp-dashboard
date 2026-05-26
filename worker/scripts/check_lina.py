"""Scrape & persist 간병인보험 / 치매보험 NP + 간병치매보험 SV again."""
from worker.db import connect
from worker.lib.naver_search import scrape_brands_for_keyword
from worker.jobs.brand_scrape import fetch_business_name, _persist_kg_brands

TARGETS = [
    ("간병치매보험", "SEARCHING_VIEW"),
    ("간병인보험", "NEW_PRODUCT"),
    ("치매보험", "NEW_PRODUCT"),
]


def find_active_rkg(conn, kw, product_code):
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
        return cur.fetchone()


with connect() as conn:
    for kw, prod in TARGETS:
        info = find_active_rkg(conn, kw, prod)
        if not info:
            print(f"[skip] {kw} ({prod})")
            continue
        rkg_id, max_brands = info
        raw_slots = scrape_brands_for_keyword(kw, prod)
        slots = [s for s in raw_slots if s.product == prod][:max_brands]
        biz = {}
        for s in slots:
            if s.destination_url and s.destination_url not in biz:
                biz[s.destination_url] = fetch_business_name(s.destination_url)
        _persist_kg_brands(rkg_id, slots, biz, conn=conn)
        conn.commit()
        if slots:
            names = "; ".join(f"slot{s.slot_no}: {s.display_name[:40]} ({biz.get(s.destination_url)})" for s in slots)
            print(f"[ok] {kw} ({prod}) → {names}")
        else:
            print(f"[ok] {kw} ({prod}) → 0 slots")
