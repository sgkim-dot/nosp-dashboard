from datetime import date
from pathlib import Path

from worker.csv_parsers import parse_bid_info_csv, parse_winning_bid_csv

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_bid_info_csv_skips_preamble():
    rows = list(parse_bid_info_csv(FIXTURES / "sample_bid_info_searching.csv"))
    assert len(rows) == 3


def test_parse_bid_info_csv_parses_round_202624():
    rows = list(parse_bid_info_csv(FIXTURES / "sample_bid_info_searching.csv"))
    r = next(row for row in rows if row.round_no == 202624)
    assert r.period_start == date(2026, 6, 8)
    assert r.period_end == date(2026, 6, 14)
    assert r.category_lvl1 == "금융"
    assert r.category_lvl2 == "금융상품"
    assert r.keyword_group == "__테스트_실비보험__"
    assert r.min_bid_price == 810_000
    assert r.regular_announce_date == date(2026, 5, 26)
    assert r.rebid_announce_date == date(2026, 6, 2)
    assert r.bid_status == "입찰가능(1구좌)"
    assert r.empty_slots == 1


def test_parse_bid_info_csv_handles_zero_empty_slots():
    rows = list(parse_bid_info_csv(FIXTURES / "sample_bid_info_searching.csv"))
    r = next(row for row in rows if row.round_no == 202622)
    assert r.empty_slots == 0


def test_parse_bid_info_csv_handles_old_11_column_format():
    rows = list(parse_bid_info_csv(FIXTURES / "sample_bid_info_searching_old_format.csv"))
    assert len(rows) == 1
    r = rows[0]
    assert r.round_no == 202552
    assert r.bid_status is None
    assert r.empty_slots is None
    assert r.keyword_group == "__테스트_old__"


def test_parse_winning_bid_csv_returns_rows():
    rows = list(parse_winning_bid_csv(FIXTURES / "sample_winning_searching.csv"))
    assert len(rows) == 1
    assert rows[0].keyword_group == "__테스트_실비보험__"
    assert rows[0].recent_winning_bid == 810_000
