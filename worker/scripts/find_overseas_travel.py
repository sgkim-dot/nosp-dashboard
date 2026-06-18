"""Find rkg_id for 해외여행자보험 NP active round."""
from worker.db import connect

with connect() as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rkg.id, kg.search_keyword, kg.name, p.code AS product_code,
                   r.round_no, r.period_start, r.period_end,
                   rkg.total_slots, rkg.brands_scraped_at,
                   (SELECT COUNT(*) FROM round_brands rb WHERE rb.round_keyword_group_id = rkg.id) AS caught
            FROM round_keyword_groups rkg
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN rounds r ON r.id = rkg.round_id
            JOIN products p ON p.id = kg.product_id
            WHERE kg.search_keyword LIKE '%해외여행자보험%' OR kg.name LIKE '%해외여행자보험%'
            ORDER BY r.id DESC, rkg.id DESC
            LIMIT 20
            """
        )
        rows = cur.fetchall()
        print(f"=== {len(rows)} candidates ===")
        for row in rows:
            print(row)
