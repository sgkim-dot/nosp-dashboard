"""Inspect any brand rows / round_brands that might be related to 아이배냇 / ivenet."""
from worker.db import connect

with connect() as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, business_name, display_name, aliases
            FROM brands
            WHERE business_name ILIKE '%ivenet%'
               OR business_name ILIKE '%아이배냇%'
               OR display_name ILIKE '%아이배냇%'
            ORDER BY id
            """
        )
        rows = cur.fetchall()
        print(f"=== brands matching ivenet/아이배냇 ({len(rows)} rows) ===")
        for r in rows:
            print(f"  id={r[0]:<5} business={r[1]!r:<45} display={r[2]!r:<15} aliases={r[3]!r}")

        # How many round_brands rows reference each brand?
        if rows:
            ids = [r[0] for r in rows]
            cur.execute(
                "SELECT brand_id, COUNT(*) FROM round_brands WHERE brand_id = ANY(%s) GROUP BY brand_id",
                (ids,),
            )
            print("\n=== round_brands usage ===")
            for r in cur.fetchall():
                print(f"  brand_id={r[0]:<5} uses={r[1]}")

        # Look at sample round_brands rows: their display_name, sub_title
        if rows:
            ids = [r[0] for r in rows]
            cur.execute(
                """
                SELECT rb.brand_id, rb.display_name, rb.sub_title, kg.name
                FROM round_brands rb
                LEFT JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
                LEFT JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
                WHERE rb.brand_id = ANY(%s)
                LIMIT 10
                """,
                (ids,),
            )
            print("\n=== sample round_brands ===")
            for r in cur.fetchall():
                print(f"  brand_id={r[0]:<5} display={r[1]!r:<60} sub_title={r[2]!r:<40} kg={r[3]!r}")
