"""Check SV 간병치매보험 + test scrape now."""
from worker.db import connect
from worker.lib.naver_search import scrape_brands_for_keyword
from worker.jobs.brand_scrape import fetch_business_name

KW = "간병치매보험"

with connect() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT p.code, rkg.id, r.round_no,
              EXISTS(SELECT 1 FROM round_brands rb WHERE rb.round_keyword_group_id = rkg.id) AS has_brand
            FROM round_keyword_groups rkg
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN rounds r ON r.id = rkg.round_id
            JOIN products p ON p.id = r.product_id
            WHERE kg.name = %s
              AND CURRENT_DATE BETWEEN r.period_start AND r.period_end
        """, (KW,))
        for code, rid, rno, has in cur.fetchall():
            print(f"[{code}] active RKG id={rid} round={rno} has_brand={has}")

# Live test BOTH products
for prod in ("SEARCHING_VIEW", "NEW_PRODUCT"):
    print(f"\n=== Live scrape {KW} ({prod}) ===")
    slots = scrape_brands_for_keyword(KW, prod)
    filtered = [s for s in slots if s.product == prod]
    for s in filtered:
        host = fetch_business_name(s.destination_url) if s.destination_url else None
        print(f"  slot={s.slot_no} name={s.display_name!r} host={host}")
    if not filtered:
        print("  (no slots)")
