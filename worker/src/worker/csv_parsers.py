import csv
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path

from worker.models import BidInfoRow, WinningBidRow

BID_INFO_HEADER = "집행회차"
WINNING_HEADER = "대분류"

_DATE = re.compile(r"^\d{8}$")


def _parse_date(s: str) -> date:
    s = s.strip()
    if not _DATE.match(s):
        raise ValueError(f"unexpected date format: {s!r}")
    return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))


def _parse_date_range(s: str) -> tuple[date, date]:
    a, b = s.split("~")
    return _parse_date(a), _parse_date(b)


def _iter_data_rows(path: Path, header_first_col: str) -> Iterator[list[str]]:
    """Yield csv rows starting after the header line whose first column matches."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        in_data = False
        headers: list[str] = []
        for row in reader:
            if not row:
                continue
            if not in_data:
                if row[0].strip() == header_first_col:
                    in_data = True
                    headers = [c.strip() for c in row]
                continue
            if len(row) < len(headers):
                continue
            yield row


def parse_bid_info_csv(path: Path) -> Iterator[BidInfoRow]:
    for row in _iter_data_rows(path, BID_INFO_HEADER):
        period_start, period_end = _parse_date_range(row[1])
        reg_start, reg_end = _parse_date_range(row[7])
        rebid_start, rebid_end = _parse_date_range(row[9])
        empty_str = row[12].strip()
        empty_slots = int(empty_str) if empty_str.isdigit() else 0
        yield BidInfoRow(
            round_no=int(row[0]),
            period_start=period_start,
            period_end=period_end,
            category_lvl1=row[2].strip(),
            category_lvl2=row[3].strip(),
            keyword_group=row[4].strip(),
            reference_query_volume=int(row[5]),
            min_bid_price=int(row[6]),
            regular_bid_start=reg_start,
            regular_bid_end=reg_end,
            regular_announce_date=_parse_date(row[8]),
            rebid_start=rebid_start,
            rebid_end=rebid_end,
            rebid_announce_date=_parse_date(row[10]),
            bid_status=row[11].strip(),
            empty_slots=empty_slots,
        )


def parse_winning_bid_csv(path: Path) -> Iterator[WinningBidRow]:
    for row in _iter_data_rows(path, WINNING_HEADER):
        yield WinningBidRow(
            category_lvl1=row[0].strip(),
            category_lvl2=row[1].strip(),
            keyword_group=row[2].strip(),
            recent_winning_bid=int(row[3]),
        )
