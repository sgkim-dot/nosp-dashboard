"""Add search_keyword override column to keyword_groups.

If set, brand_scrape uses this value instead of `name` as the Naver
search query. Display in the dashboard stays the original `name`.
"""
from worker.db import connect

with connect() as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            ALTER TABLE keyword_groups
            ADD COLUMN IF NOT EXISTS search_keyword varchar(128)
            """
        )
        # Set the requested override for SV 다이렉트인보험.
        cur.execute(
            """
            UPDATE keyword_groups kg
            SET search_keyword = %s
            FROM products p
            WHERE kg.product_id = p.id
              AND p.code = 'SEARCHING_VIEW'
              AND kg.name = '다이렉트인보험'
            RETURNING kg.id, kg.name, kg.search_keyword
            """,
            ('다이렉트보험',),
        )
        for r in cur.fetchall():
            print(f"  set: kg_id={r[0]} name={r[1]!r} search_keyword={r[2]!r}")
    conn.commit()
print("OK")
