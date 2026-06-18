"""Show round_brands for 해외여행자보험 (rkg=308905) after re-scrape."""
from worker.db import connect

RKG_ID = 308905

with connect() as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='round_brands'
            ORDER BY ordinal_position
            """
        )
        print("round_brands columns:", [r[0] for r in cur.fetchall()])

        cur.execute(
            """
            SELECT rb.*, b.business_name, b.display_name AS brand_display
            FROM round_brands rb
            JOIN brands b ON b.id = rb.brand_id
            WHERE rb.round_keyword_group_id = %s
            ORDER BY rb.slot_no
            """,
            (RKG_ID,),
        )
        rows = cur.fetchall()
        cols = [d.name for d in cur.description]
        print(f"\nround_brands rows ({len(rows)}):")
        for r in rows:
            print(dict(zip(cols, r)))
