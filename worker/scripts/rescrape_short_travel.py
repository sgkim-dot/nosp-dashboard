"""Force re-scrape of NP 단기여행자보험 (rkg=304319) — never scraped this round."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from worker.db import connect
from worker.jobs.brand_scrape import scrape_brands_for_active_rounds

RKG_ID = 304319

with connect() as conn:
    result = scrape_brands_for_active_rounds(conn, rkg_ids=[RKG_ID])
    print(f"Result: {result}")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rb.slot_no, b.business_name, b.display_name AS brand_dn,
                   rb.display_name, rb.sub_title, rb.source, rb.confidence
            FROM round_brands rb
            JOIN brands b ON b.id = rb.brand_id
            WHERE rb.round_keyword_group_id = %s
            ORDER BY rb.slot_no
            """,
            (RKG_ID,),
        )
        rows = cur.fetchall()
        print(f"\nround_brands ({len(rows)} rows):")
        for r in rows:
            print(f"  slot={r[0]}  bn={r[1]!r}  brand_dn={r[2]!r}")
            print(f"    ad_title={r[3]!r}  sub={r[4]!r}  src={r[5]} conf={r[6]}")
