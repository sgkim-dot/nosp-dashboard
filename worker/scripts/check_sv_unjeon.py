"""Check the status of SV 운전자보험 in the scrape + try scraping it now."""
from worker.db import connect
from worker.lib.naver_search import scrape_brands_for_keyword
from worker.jobs.brand_scrape import fetch_business_name

with connect() as conn:
    with conn.cursor() as cur:
        # Find the SV 운전자보험 RKG for active round
        cur.execute("""
            SELECT rkg.id, r.round_no, r.period_start, r.period_end, p.code
            FROM round_keyword_groups rkg
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN rounds r ON r.id = rkg.round_id
            JOIN products p ON p.id = r.product_id
            WHERE kg.name = '운전자보험'
              AND p.code = 'SEARCHING_VIEW'
              AND CURRENT_DATE BETWEEN r.period_start AND r.period_end
        """)
        for r in cur.fetchall():
            print(f"SV 운전자보험 active RKG: id={r[0]} round={r[1]} {r[2]}~{r[3]}")

        # Check if any brand is attached
        cur.execute("""
            SELECT b.display_name, b.business_name, rb.captured_at
            FROM round_brands rb
            JOIN brands b ON b.id = rb.brand_id
            JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN products p ON p.id = rkg.round_id::int  -- dummy
            WHERE kg.name = '운전자보험'
        """)
        rows = cur.fetchall()
        if rows:
            print("Existing brand rows for 운전자보험:")
            for r in rows:
                print(f"  {r}")
        else:
            print("No brand rows for 운전자보험 yet")

print("\n=== Scraping SV 운전자보험 from PC ===")
slots = scrape_brands_for_keyword("운전자보험", "SEARCHING_VIEW")
for s in slots:
    if s.product != "SEARCHING_VIEW":
        continue
    host = fetch_business_name(s.destination_url) if s.destination_url else None
    print(f"  SV slot={s.slot_no} name={s.display_name!r}")
    print(f"    host={host}")
if not [s for s in slots if s.product == "SEARCHING_VIEW"]:
    print("  (no SV slots on PC)")
