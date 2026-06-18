"""Find rkg_id for 단기여행자보험 active NP round."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from worker.db import connect

with connect() as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rkg.id, kg.name, COALESCE(kg.search_keyword, kg.name) AS search_kw,
                   p.code, r.round_no, r.period_start, r.period_end,
                   rkg.total_slots, rkg.empty_slots, rkg.regular_winning_bid,
                   rkg.brands_scraped_at,
                   (SELECT COUNT(*) FROM round_brands rb WHERE rb.round_keyword_group_id = rkg.id) AS caught
            FROM round_keyword_groups rkg
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN rounds r ON r.id = rkg.round_id
            JOIN products p ON p.id = kg.product_id
            WHERE (kg.name LIKE '%단기여행%' OR kg.search_keyword LIKE '%단기여행%')
            ORDER BY r.id DESC LIMIT 20
            """
        )
        for row in cur.fetchall():
            print(row)
