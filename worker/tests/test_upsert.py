import pytest

from worker.upsert import upsert_category_pair, upsert_keyword_group

pytestmark = pytest.mark.db


def test_upsert_category_pair_creates_both_levels(db_conn):
    lvl1_id, lvl2_id = upsert_category_pair(db_conn, "금융", "금융상품")
    assert lvl1_id and lvl2_id and lvl1_id != lvl2_id

    # idempotent
    lvl1_id2, lvl2_id2 = upsert_category_pair(db_conn, "금융", "금융상품")
    assert lvl1_id == lvl1_id2
    assert lvl2_id == lvl2_id2


def test_upsert_keyword_group_is_unique_per_product(db_conn):
    _, lvl2 = upsert_category_pair(db_conn, "금융", "금융상품")

    cur = db_conn.cursor()
    cur.execute("SELECT id FROM products WHERE code = 'SEARCHING_VIEW'")
    sv_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM products WHERE code = 'NEW_PRODUCT'")
    np_id = cur.fetchone()[0]

    sv_kg = upsert_keyword_group(db_conn, sv_id, lvl2, "실비보험")
    np_kg = upsert_keyword_group(db_conn, np_id, lvl2, "실비보험")
    assert sv_kg != np_kg

    again = upsert_keyword_group(db_conn, sv_id, lvl2, "실비보험")
    assert again == sv_kg


from datetime import date

from worker.upsert import upsert_round, upsert_round_keyword_group


def test_upsert_round_is_idempotent(db_conn):
    cur = db_conn.cursor()
    cur.execute("SELECT id FROM products WHERE code = 'SEARCHING_VIEW'")
    sv_id = cur.fetchone()[0]

    common = dict(
        product_id=sv_id,
        round_no=202624,
        period_start=date(2026, 6, 8),
        period_end=date(2026, 6, 14),
        regular_bid_start=date(2026, 5, 19),
        regular_bid_end=date(2026, 5, 25),
        regular_announce_date=date(2026, 5, 26),
        rebid_start=date(2026, 5, 27),
        rebid_end=date(2026, 6, 1),
        rebid_announce_date=date(2026, 6, 2),
    )
    r1 = upsert_round(db_conn, **common)
    r2 = upsert_round(db_conn, **common)
    assert r1 == r2


def test_upsert_round_keyword_group_updates_status(db_conn):
    cur = db_conn.cursor()
    cur.execute("SELECT id FROM products WHERE code = 'SEARCHING_VIEW'")
    sv_id = cur.fetchone()[0]

    _, lvl2 = upsert_category_pair(db_conn, "금융", "금융상품")
    kg_id = upsert_keyword_group(db_conn, sv_id, lvl2, "실비보험")
    round_id = upsert_round(
        db_conn,
        product_id=sv_id,
        round_no=202624,
        period_start=date(2026, 6, 8),
        period_end=date(2026, 6, 14),
    )

    rkg1 = upsert_round_keyword_group(
        db_conn,
        round_id=round_id,
        keyword_group_id=kg_id,
        reference_query_volume=15700,
        min_bid_price=810_000,
        bid_status="입찰가능",
        empty_slots=1,
    )
    rkg2 = upsert_round_keyword_group(
        db_conn,
        round_id=round_id,
        keyword_group_id=kg_id,
        reference_query_volume=15700,
        min_bid_price=810_000,
        bid_status="입찰기간종료",
        empty_slots=0,
    )
    assert rkg1 == rkg2

    cur.execute("SELECT bid_status, empty_slots FROM round_keyword_groups WHERE id = %s", (rkg1,))
    status, slots = cur.fetchone()
    assert status == "입찰기간종료"
    assert slots == 0
