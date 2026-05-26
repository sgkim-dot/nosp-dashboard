"""Diagnose which rounds have brand data."""
from worker.db import connect

with connect() as conn:
    with conn.cursor() as cur:
        # Brands grouped by round
        cur.execute("""
            SELECT r.round_no, p.code, COUNT(rb.id), COUNT(DISTINCT rkg.id)
            FROM round_brands rb
            JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
            JOIN rounds r ON r.id = rkg.round_id
            JOIN products p ON p.id = r.product_id
            GROUP BY r.round_no, p.code
            ORDER BY r.round_no DESC
        """)
        print("Brands per round:")
        for rn, code, brands, kgs in cur.fetchall():
            print(f"  {code:18s} round {rn}: {brands} brand rows in {kgs} KGs")

        # What rounds exist in DB (latest)
        cur.execute("""
            SELECT p.code, r.round_no, r.period_start, r.period_end,
                   CASE WHEN CURRENT_DATE BETWEEN r.period_start AND r.period_end THEN 'ACTIVE'
                        WHEN r.period_start > CURRENT_DATE THEN 'FUTURE'
                        ELSE 'PAST' END AS status
            FROM rounds r
            JOIN products p ON p.id = r.product_id
            WHERE r.round_no > 202618
            ORDER BY p.code, r.round_no DESC
        """)
        print("\nRecent rounds:")
        for code, rn, ps, pe, status in cur.fetchall():
            print(f"  {code:18s} round {rn}: {ps} ~ {pe}  [{status}]")
