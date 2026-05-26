"""Wipe ALL round_brands + bad __unverified__ brand rows before fresh scrape.

All previously-scraped data is suspect (wrong selectors), so we start fresh.
"""
from worker.db import connect

with connect() as conn:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM round_brands")
        print(f"round_brands deleted: {cur.rowcount}")
        cur.execute("DELETE FROM brands WHERE business_name LIKE '__unverified__::%'")
        print(f"__unverified__ brands deleted: {cur.rowcount}")
        cur.execute("SELECT COUNT(*) FROM brands")
        print(f"remaining brand rows: {cur.fetchone()[0]}")
        conn.commit()
