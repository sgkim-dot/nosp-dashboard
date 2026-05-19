from datetime import date

from pydantic import BaseModel


class BidInfoRow(BaseModel):
    round_no: int
    period_start: date
    period_end: date
    category_lvl1: str
    category_lvl2: str
    keyword_group: str
    reference_query_volume: int
    min_bid_price: int
    regular_bid_start: date
    regular_bid_end: date
    regular_announce_date: date
    rebid_start: date
    rebid_end: date
    rebid_announce_date: date
    bid_status: str
    empty_slots: int


class WinningBidRow(BaseModel):
    category_lvl1: str
    category_lvl2: str
    keyword_group: str
    recent_winning_bid: int
