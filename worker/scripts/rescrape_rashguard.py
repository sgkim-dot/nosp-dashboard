"""Quick re-scrape for 래쉬가드 (rkg=304629) — verify product-filtered detected_slot_count."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from worker.db import connect
from worker.jobs.brand_scrape import scrape_brands_for_active_rounds

RKG_ID = 304629

with connect() as conn:
    result = scrape_brands_for_active_rounds(conn, rkg_ids=[RKG_ID])
    print(f"Result: {result}")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rkg.detected_slot_count,
                   (SELECT COUNT(*) FROM round_brands rb WHERE rb.round_keyword_group_id = rkg.id) AS caught
            FROM round_keyword_groups rkg WHERE rkg.id = %s
            """,
            (RKG_ID,),
        )
        d, c = cur.fetchone()
        print(f"detected_slot_count={d}, caught={c}")
