from worker.db import connect

with connect() as conn, conn.cursor() as cur:
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name='round_brands'
        ORDER BY ordinal_position
    """)
    print("round_brands:")
    for c in cur.fetchall():
        print(f"  {c[0]}  {c[1]}")
