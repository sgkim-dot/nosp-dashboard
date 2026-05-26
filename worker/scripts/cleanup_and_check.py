"""Pre-rescrape cleanup + check."""
from worker.db import connect

with connect() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM round_brands")
        print(f"round_brands rows: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(*) FROM brands WHERE business_name LIKE '__unverified__::%'")
        print(f"__unverified__ brands: {cur.fetchone()[0]}")
        # Delete any leftover orphan __unverified__ brand rows
        cur.execute(
            """
            DELETE FROM brands b
            WHERE b.business_name LIKE '__unverified__::%'
              AND NOT EXISTS (SELECT 1 FROM round_brands rb WHERE rb.brand_id = b.id)
            """
        )
        print(f"orphan __unverified__ deleted: {cur.rowcount}")
        conn.commit()
