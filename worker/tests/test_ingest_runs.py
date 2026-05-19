import pytest

from worker.upsert import complete_ingest_run, fail_ingest_run, start_ingest_run

pytestmark = pytest.mark.db


def test_start_then_complete_ingest_run(db_conn):
    run_id = start_ingest_run(db_conn, run_type="csv_bid_info", file_path="raw/foo.csv")
    assert isinstance(run_id, int)

    complete_ingest_run(
        db_conn, run_id=run_id, rows_total=100, rows_inserted=80, rows_updated=20
    )

    cur = db_conn.cursor()
    cur.execute(
        "SELECT status, rows_inserted, rows_updated FROM ingest_runs WHERE id = %s",
        (run_id,),
    )
    status, ins, upd = cur.fetchone()
    assert status == "success"
    assert ins == 80
    assert upd == 20


def test_start_then_fail_ingest_run(db_conn):
    run_id = start_ingest_run(db_conn, run_type="csv_winning", file_path="raw/bar.csv")
    fail_ingest_run(db_conn, run_id=run_id, error_message="boom")

    cur = db_conn.cursor()
    cur.execute("SELECT status, error_message FROM ingest_runs WHERE id = %s", (run_id,))
    status, err = cur.fetchone()
    assert status == "error"
    assert err == "boom"
