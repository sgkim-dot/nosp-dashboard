import pytest

from worker.lib.brand_match import upsert_brand

pytestmark = pytest.mark.db


def test_inserts_new_brand_when_no_match(db_conn):
    bid = upsert_brand(db_conn, business_name="(주)__bm_테스트__", display_name="__bm테스트__")
    assert isinstance(bid, int)
    cur = db_conn.cursor()
    cur.execute("SELECT business_name, display_name FROM brands WHERE id = %s", (bid,))
    bn, dn = cur.fetchone()
    assert bn == "(주)__bm_테스트__"
    assert dn == "__bm테스트__"


def test_matches_existing_brand_by_business_name_and_appends_alias(db_conn):
    bid1 = upsert_brand(db_conn, business_name="(주)__bm_테스트__", display_name="__bm테스트__")
    bid2 = upsert_brand(db_conn, business_name="(주)__bm_테스트__", display_name="__bm테스트 다이렉트__")
    assert bid1 == bid2
    cur = db_conn.cursor()
    cur.execute("SELECT aliases FROM brands WHERE id = %s", (bid1,))
    aliases = cur.fetchone()[0]
    assert "__bm테스트 다이렉트__" in aliases


def test_fuzzy_matches_by_display_name_when_no_business_name(db_conn):
    bid1 = upsert_brand(db_conn, business_name="(주)__bm_테스트__", display_name="__bm테스트__")
    bid2 = upsert_brand(db_conn, business_name=None, display_name="__bm테스트__")
    assert bid1 == bid2
