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
    bid_status: str | None
    empty_slots: int | None


class WinningBidRow(BaseModel):
    category_lvl1: str
    category_lvl2: str
    keyword_group: str
    recent_winning_bid: int


class SlotExtract(BaseModel):
    """A single ad slot extracted from a Naver search result page."""

    product: str  # "SEARCHING_VIEW" | "NEW_PRODUCT"
    slot_no: int
    display_name: str       # main title (.tit)
    sub_title: str | None = None    # NP only: small line above title (.sub_tit)
    description: str | None = None  # NP only: lines below title (.desc, joined)
    destination_url: str | None
