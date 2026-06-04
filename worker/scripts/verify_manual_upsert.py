"""Verify the manual upsert: counts and sample by round/product."""
from worker.db import connect

with connect() as conn:
    with conn.cursor() as cur:
        # Total rows added with source='manual'
        cur.execute("SELECT COUNT(*) FROM round_brands WHERE source = 'manual'")
        total = cur.fetchone()[0]
        print(f"Total round_brands with source='manual': {total}")

        # Breakdown by product and round
        cur.execute(
            """
            SELECT p.code, r.round_no, COUNT(*) AS rows
            FROM round_brands rb
            JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
            JOIN rounds r ON r.id = rkg.round_id
            JOIN products p ON p.id = r.product_id
            WHERE rb.source = 'manual'
            GROUP BY p.code, r.round_no
            ORDER BY p.code, r.round_no
            """
        )
        print("\nBy product / round:")
        for code, rno, n in cur.fetchall():
            print(f"  {code:<15} r{rno}: {n} rows")

        # Sample with brand display_names
        cur.execute(
            """
            SELECT r.round_no, kg.name, p.code, rb.slot_no, b.display_name
            FROM round_brands rb
            JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
            JOIN rounds r ON r.id = rkg.round_id
            JOIN products p ON p.id = r.product_id
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
            JOIN brands b ON b.id = rb.brand_id
            WHERE rb.source = 'manual'
            ORDER BY p.code, r.round_no, kg.name, rb.slot_no
            LIMIT 20
            """
        )
        print("\nFirst 20 inserted rows:")
        for r in cur.fetchall():
            print(f"  r{r[0]} {r[2]:<15} {r[1]:<20} slot={r[3]} brand={r[4]!r}")

        # New brands inserted
        cur.execute(
            """
            SELECT id, business_name, display_name
            FROM brands
            WHERE display_name IN ('교보생명', '교보라이프플래닛', '신한EZ손해보험', '한화손해보험')
            ORDER BY id
            """
        )
        print("\nNewly inserted brands:")
        for r in cur.fetchall():
            print(f"  id={r[0]:<5} business={r[1]!r:<35} display={r[2]!r}")
