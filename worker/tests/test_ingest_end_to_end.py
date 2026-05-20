from pathlib import Path

import pytest

from worker.ingest import ingest_csv

REPO_ROOT = Path(__file__).resolve().parents[2]

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
        JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
        WHERE p.code = 'SEARCHING_VIEW' AND kg.name = '__테스트_실비보험__'
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
        JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
        WHERE rkg.regular_winning_bid IS NOT NULL
          AND kg.name = '__테스트_실비보험__'
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


def test_ingest_routes_anniversary_rows_to_anniversary_product(db_conn):
    """Anniversary rows (기념일/기념일) must land under ANNIVERSARY, not NEW_PRODUCT."""
    fixture = REPO_ROOT / "predata" / "신제품_회차별입찰정보_20260205.csv"
    if not fixture.exists():
        pytest.skip(f"predata fixture missing: {fixture}")

    ingest_csv(
        db_conn,
        path=fixture,
        product_code="NEW_PRODUCT",
        kind="bid_info",
    )

    cur = db_conn.cursor()
    # Anniversary rows should land under product ANNIVERSARY
    cur.execute("""
        SELECT COUNT(*)
        FROM round_keyword_groups rkg
        JOIN rounds r ON r.id = rkg.round_id
        JOIN products p ON p.id = r.product_id
        JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
        WHERE p.code = 'ANNIVERSARY' AND kg.name = '설날'
    """)
    anniv_count = cur.fetchone()[0]
    assert anniv_count == 1, f"expected 1 anniversary row for 설날, got {anniv_count}"

    # Anniversary rows should NOT have leaked into NEW_PRODUCT
    cur.execute("""
        SELECT COUNT(*)
        FROM round_keyword_groups rkg
        JOIN rounds r ON r.id = rkg.round_id
        JOIN products p ON p.id = r.product_id
        JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
        WHERE p.code = 'NEW_PRODUCT' AND kg.name = '설날'
    """)
    np_count = cur.fetchone()[0]
    assert np_count == 0
