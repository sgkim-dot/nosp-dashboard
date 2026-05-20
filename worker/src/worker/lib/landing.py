"""Stage 2: extract 사업자등록상호 from landing-page HTML footers."""

from __future__ import annotations

import re
from collections.abc import Iterable

from bs4 import BeautifulSoup

# Each pattern captures the business name in group(1). First match wins.
# Delimiters after the name: 대표, 사업자, 주소, 전화, TEL, ㅣ, |, ·, newline, tag
_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"상호\s*명?\s*[:：]\s*([^\n<,|·ㅣ]+?)(?=\s*(?:대표|사업자|주소|전화|TEL|ㅣ|\||·|$|<))",
        re.IGNORECASE,
    ),
    re.compile(
        r"회사명\s*[:：]\s*([^\n<,|·ㅣ]+?)(?=\s*(?:대표|사업자|주소|전화|TEL|ㅣ|\||·|$|<))",
        re.IGNORECASE,
    ),
    re.compile(
        r"법인명\s*[:：]\s*([^\n<,|·ㅣ]+?)(?=\s*(?:대표|사업자|주소|전화|TEL|ㅣ|\||·|$|<))",
        re.IGNORECASE,
    ),
    re.compile(
        r"商號\s*[:：]\s*([^\n<,|·ㅣ]+?)(?=\s*(?:대표|사업자|주소|전화|TEL|ㅣ|\||·|$|<))",
        re.IGNORECASE,
    ),
]


def _candidate_texts(html: str) -> Iterable[str]:
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.find_all("footer"):
        yield el.get_text(" ", strip=True)
    for el in soup.find_all(class_=re.compile(r"footer", re.IGNORECASE)):
        yield el.get_text(" ", strip=True)
    body = soup.find("body")
    if body:
        yield body.get_text(" ", strip=True)[-3000:]
    # Fallback: raw text of entire HTML (handles embedded JSON / script patterns)
    yield soup.get_text(" ", strip=True)[-3000:]
    # Also search raw HTML for patterns that might be HTML-encoded or in spans
    yield html[-5000:]


def extract_business_name(html: str) -> str | None:
    seen_already: set[str] = set()
    for text in _candidate_texts(html):
        if text in seen_already:
            continue
        seen_already.add(text)
        for pat in _PATTERNS:
            m = pat.search(text)
            if m:
                name = m.group(1).strip().rstrip("·•-—()ㅣ| ")
                if 2 <= len(name) <= 60:
                    return name
    return None
