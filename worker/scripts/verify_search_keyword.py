"""Verify the search_keyword override is in place and queryable."""
from worker.db import connect

with connect() as conn:
    with conn.cursor() as cur:
        # Confirm the column exists
        cur.execute(
            """
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'keyword_groups' AND column_name = 'search_keyword'
            """
        )
        col = cur.fetchone()
        print(f"Column: {col}")

        # Confirm only the targeted row was updated
        cur.execute(
            """
            SELECT kg.id, p.code, kg.name, kg.search_keyword
            FROM keyword_groups kg
            JOIN products p ON p.id = kg.product_id
            WHERE kg.search_keyword IS NOT NULL
            ORDER BY kg.id
            """
        )
        print("\nRows with search_keyword override:")
        for r in cur.fetchall():
            print(f"  kg_id={r[0]} product={r[1]} name={r[2]!r} search_keyword={r[3]!r}")

        # Simulate what brand_scrape's _fetch_work_list would return for SV 다이렉트인보험
        cur.execute(
            """
            SELECT DISTINCT rkg.id,
                            COALESCE(kg.search_keyword, kg.name) AS scrape_keyword,
                            kg.name AS display_name,
                            p.code
            FROM round_keyword_groups rkg
            JOIN rounds r ON r.id = rkg.round_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN products p ON p.id = r.product_id
            WHERE p.code = 'SEARCHING_VIEW'
              AND kg.name = '다이렉트인보험'
              AND r.period_start <= CURRENT_DATE AND r.period_end >= CURRENT_DATE
            """
        )
        print("\nSimulated scrape work-list row for active SV 다이렉트인보험:")
        for r in cur.fetchall():
            print(f"  rkg={r[0]} → scrape_keyword={r[1]!r} (display='{r[2]}', product={r[3]})")
