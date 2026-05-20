from pathlib import Path

from worker.lib.landing import extract_business_name

FIXTURES = Path(__file__).parent / "fixtures" / "landing"


def test_extracts_business_name_from_jacomo():
    html = (FIXTURES / "jacomo.html").read_text(encoding="utf-8")
    name = extract_business_name(html)
    assert name is not None
    # jacomo footer: 상호명: 초이스 (자코모 JACOMO)
    assert "자코모" in name or "초이스" in name


def test_extracts_business_name_from_dentium():
    html = (FIXTURES / "dentium.html").read_text(encoding="utf-8")
    name = extract_business_name(html)
    assert name is not None
    # dentium footer: 법인명 : (주)덴티움
    assert "덴티움" in name


def test_returns_none_when_no_business_name():
    html = (FIXTURES / "minimal_footer.html").read_text(encoding="utf-8")
    assert extract_business_name(html) is None
