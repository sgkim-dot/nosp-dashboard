from datetime import date
from unittest.mock import patch

import pytest

from worker.jobs.brand_scrape import scrape_brands_for_active_rounds
from worker.models import SlotExtract
from worker.upsert import (
    upsert_category_pair,
    upsert_keyword_group,
    upsert_round,
    upsert_round_keyword_group,
)

pytestmark = pytest.mark.db


@pytest.fixture
def _two_active_rkgs(db_conn):
    cur = db_conn.cursor()
    cur.execute("SELECT id FROM products WHERE code = 'SEARCHING_VIEW'")
    sv_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM products WHERE code = 'NEW_PRODUCT'")
    np_id = cur.fetchone()[0]

    _, lvl2 = upsert_category_pair(db_conn, "__bs_금융__", "__bs_금융상품__")
    sv_kg = upsert_keyword_group(db_conn, sv_id, lvl2, "__bs_실비__")
    np_kg = upsert_keyword_group(db_conn, np_id, lvl2, "__bs_쇼파__")

    today = date.today()
    sv_round = upsert_round(
        db_conn,
        product_id=sv_id,
        round_no=999001,
        period_start=today,
        period_end=today,
    )
    np_round = upsert_round(
        db_conn,
        product_id=np_id,
        round_no=999002,
        period_start=today,
        period_end=today,
    )
    sv_rkg = upsert_round_keyword_group(db_conn, round_id=sv_round, keyword_group_id=sv_kg)
    np_rkg = upsert_round_keyword_group(db_conn, round_id=np_round, keyword_group_id=np_kg)
    return {"sv_rkg": sv_rkg, "np_rkg": np_rkg}


def _fake_scrape(keyword: str) -> list[SlotExtract]:
    if "실비" in keyword:
        return [
            SlotExtract(
                product="SEARCHING_VIEW",
                slot_no=1,
                display_name="삼성화재",
                destination_url="https://samsungfire.example/",
            )
        ]
    if "쇼파" in keyword:
        return [
            SlotExtract(
                product="NEW_PRODUCT",
                slot_no=1,
                display_name="자코모",
                destination_url="https://jacomo.example/",
            ),
            SlotExtract(
                product="NEW_PRODUCT",
                slot_no=2,
                display_name="도미실",
                destination_url="https://domisil.example/",
            ),
        ]
    return []


def _fake_business_name(url: str) -> str | None:
    return {
        "https://samsungfire.example/": "삼성화재해상보험(주)",
        "https://jacomo.example/": "(주)자코모인터내셔널",
        "https://domisil.example/": "(주)도미실가구",
    }.get(url)


def test_scrape_brands_populates_round_brands(db_conn, _two_active_rkgs):
    test_rkg_ids = [_two_active_rkgs["sv_rkg"], _two_active_rkgs["np_rkg"]]
    with (
        patch("worker.jobs.brand_scrape.scrape_brands_for_keyword", side_effect=_fake_scrape),
        patch("worker.jobs.brand_scrape.fetch_business_name", side_effect=_fake_business_name),
    ):
        result = scrape_brands_for_active_rounds(db_conn, delay_seconds=0, rkg_ids=test_rkg_ids)

    assert result["slots_inserted"] == 3
    assert result["keyword_groups_scraped"] == 2

    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT b.display_name
        FROM round_brands rb
        JOIN brands b ON b.id = rb.brand_id
        WHERE rb.round_keyword_group_id IN (%s, %s)
        ORDER BY b.display_name
        """,
        (_two_active_rkgs["sv_rkg"], _two_active_rkgs["np_rkg"]),
    )
    names = [r[0] for r in cur.fetchall()]
    assert "삼성화재" in names
    assert "자코모" in names
    assert "도미실" in names
