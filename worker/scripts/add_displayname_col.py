from worker.db import connect
with connect() as conn, conn.cursor() as cur:
    cur.execute("ALTER TABLE round_brands ADD COLUMN IF NOT EXISTS display_name VARCHAR(200)")
    conn.commit()
    print("Column added (or already exists)")
