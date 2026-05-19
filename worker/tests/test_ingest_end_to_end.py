from pathlib import Path

import pytest

from worker.ingest import ingest_csv

FIXTURES = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.db


def test_ingest_bid_info_creates_rounds_and_rkg(db_conn):
    result = ingest_csv(
        db_conn,
        path=FIXTURES / "sample_bid_info_searching.csv",
        product_code="SEARCHING_VIEW",
        kind="bid_info",
    )
    assert result.rows_total == 3
    assert result.rows_inserted == 3
    assert result.rows_updated == 0

    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT r.round_no, rkg.min_bid_price, rkg.bid_status, rkg.empty_slots
        FROM round_keyword_groups rkg
        JOIN rounds r ON r.id = rkg.round_id
        JOIN products p ON p.id = r.product_id
        WHERE p.code = 'SEARCHING_VIEW'
        ORDER BY r.round_no
        """
    )
    rows = cur.fetchall()
    assert rows == [
        (202622, 590_000, "입찰기간종료", 0),
        (202623, 810_000, "입찰중지", 0),
        (202624, 810_000, "입찰가능(1구좌)", 1),
    ]


def test_ingest_winning_then_bid_info_preserves_winning(db_conn):
    # Bid info first
    ingest_csv(
        db_conn,
        path=FIXTURES / "sample_bid_info_searching.csv",
        product_code="SEARCHING_VIEW",
        kind="bid_info",
    )
    # Then winning
    result = ingest_csv(
        db_conn,
        path=FIXTURES / "sample_winning_searching.csv",
        product_code="SEARCHING_VIEW",
        kind="winning",
    )
    assert result.rows_total == 1
    assert result.rows_updated == 1

    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT r.round_no, rkg.regular_winning_bid
        FROM round_keyword_groups rkg
        JOIN rounds r ON r.id = rkg.round_id
        WHERE rkg.regular_winning_bid IS NOT NULL
        ORDER BY r.round_no DESC
        LIMIT 1
        """
    )
    round_no, winning = cur.fetchone()
    # 조회일자 = 20260519, latest regular_announce_date <= 20260519 is 20260519 (round 202623)
    assert round_no == 202623
    assert winning == 810_000


def test_ingest_is_idempotent(db_conn):
    r1 = ingest_csv(
        db_conn,
        path=FIXTURES / "sample_bid_info_searching.csv",
        product_code="SEARCHING_VIEW",
        kind="bid_info",
    )
    r2 = ingest_csv(
        db_conn,
        path=FIXTURES / "sample_bid_info_searching.csv",
        product_code="SEARCHING_VIEW",
        kind="bid_info",
    )
    assert r1.rows_inserted == 3
    assert r2.rows_inserted == 0
    assert r2.rows_updated == 3
