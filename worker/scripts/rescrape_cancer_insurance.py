"""Force re-scrape of NP 암보험 (rkg=326689) — user reported 라이나생명 노출 중."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from worker.db import connect
from worker.jobs.brand_scrape import scrape_brands_for_active_rounds

RKG_ID = 326689

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
        print(f"detected={d}, caught={c}")

        cur.execute(
            """
            SELECT rb.slot_no, b.business_name, b.display_name, rb.display_name
            FROM round_brands rb
            JOIN brands b ON b.id = rb.brand_id
            WHERE rb.round_keyword_group_id = %s
            ORDER BY rb.slot_no
            """,
            (RKG_ID,),
        )
        for r in cur.fetchall():
            print(f"  slot={r[0]} bn={r[1]!r} dn={r[2]!r} ad_title={r[3]!r}")
