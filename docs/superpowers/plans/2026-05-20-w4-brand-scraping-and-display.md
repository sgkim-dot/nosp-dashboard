# W4 — Brand Scraping & Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scrape currently-running brands per keyword group from Naver search results, normalize them by 사업자등록상호 (business name), persist into `round_brands`, then surface them on Screen 1 (chart, table, summary) and build a dedicated Screen 3 (브랜드 점유) showing 회차별 카테고리 점유 + brand details.

**Architecture:** Two-stage hybrid scraper (DOM extraction + landing-page footer parse). Stage 1 uses browser-harness to render `https://search.naver.com/...?query=<keyword>` and pulls the ad-card brand name + destination URL from the `서칭뷰` (1 slot) and `신제품검색` (up to 2 slots) areas. Stage 2 fetches each destination URL via plain HTTP and extracts `사업자등록상호` via regex over the footer. A fuzzy match (rapidfuzz) links display variants to a canonical `brands` row; new brands are inserted. The dashboard reads brand rows joined to `round_keyword_groups` and renders chips/columns.

**Tech Stack:** Python 3.13, browser-harness (already installed at `C:/Users/MADUP/Developer/browser-harness`), httpx, beautifulsoup4, rapidfuzz, psycopg, structlog, watchdog. Frontend: existing Next.js 16 + Drizzle stack.

**Spec reference:** [2026-05-19-nosp-dashboard-design.md](../specs/2026-05-19-nosp-dashboard-design.md) §2.2, §3, §4.1 JOB 3, §5.3, §5.5.

**Builds on:** W1 (`w1-complete`) + W2 (`w2-complete`).

**Order:** W4 is being done **before W3** at the user's request — brand info is the next-most-valuable signal for bid decisions.

---

## File Structure

```
worker/
├─ src/worker/
│  ├─ lib/                                 # NEW namespace for scrapers
│  │  ├─ __init__.py
│  │  ├─ naver_search.py                   # NEW: Stage 1 — DOM scrape
│  │  ├─ landing.py                        # NEW: Stage 2 — footer parse
│  │  └─ brand_match.py                    # NEW: fuzzy match + upsert
│  ├─ jobs/
│  │  └─ brand_scrape.py                   # NEW: JOB 3 entry point
│  └─ models.py                            # MODIFIED: add SlotExtract dataclass
└─ tests/
   ├─ fixtures/landing/                    # NEW: snapshot HTML for footer tests
   │  ├─ samsungfire.html
   │  ├─ casamia.html
   │  └─ minimal_footer.html
   ├─ test_landing.py                      # NEW
   ├─ test_brand_match.py                  # NEW
   └─ test_brand_scrape_e2e.py             # NEW (db-marked)

apps/dashboard/
├─ types/bid-decision.ts                   # MODIFIED: add brand fields
├─ lib/db/queries.ts                       # MODIFIED: brands in summary
├─ components/bid-decision/
│  ├─ summary-card.tsx                     # MODIFIED: real brand chips
│  ├─ trend-chart.tsx                      # MODIFIED: brand markers/tooltip
│  └─ round-table.tsx                      # MODIFIED: real brand cells
├─ app/
│  └─ brand/
│     ├─ page.tsx                          # NEW: Screen 3 (브랜드 점유)
│     └─ [brand_id]/
│        └─ page.tsx                       # NEW: brand detail
└─ components/brand/
   ├─ category-heatmap.tsx                 # NEW
   ├─ brand-detail-card.tsx                # NEW
   └─ brand-table.tsx                      # NEW
```

---

# PHASE A — Brand Scraping (Worker)

## Task 1: Explore Naver search page DOM (manual recon)

**Files:** (no code yet — produces notes for Task 2)

This is a research task. The engineer must look at real Naver search result pages and document the DOM selectors for the 서칭뷰 banner and 신제품검색 product cards. Without this, the scraper will fail on real pages.

- [ ] **Step 1: Open browser, navigate to a search result page with both ad types**

In a regular Chrome window (NOT browser-harness — we need DevTools), open:

```
https://search.naver.com/search.naver?query=실비보험
```

(`실비보험` is a SV keyword we know runs ads.)

- [ ] **Step 2: Open DevTools → Elements**

Identify the 서칭뷰 ad area. Look for:
- The container element (likely has class `searching_view`, `power_link`, or similar — names change)
- The brand title text node
- The clickable anchor whose `href` is the destination URL

Document the CSS selector / structural path to:
- `SV_AD_CONTAINER_SELECTOR`
- `SV_AD_TITLE_SELECTOR` (relative to container)
- `SV_AD_LINK_SELECTOR` (relative to container)

- [ ] **Step 3: Try a search with 신제품 ads**

Navigate to `https://search.naver.com/search.naver?query=쇼파` (NP keyword).

Identify the 신제품검색 area. It typically shows 2 product cards side-by-side. For each card:
- The card container (relative to a section element)
- The brand/product name text node
- The destination URL anchor

Document:
- `NP_SECTION_SELECTOR`
- `NP_CARD_SELECTOR` (each card)
- `NP_CARD_BRAND_SELECTOR`
- `NP_CARD_LINK_SELECTOR`

- [ ] **Step 4: Note anti-bot behaviors**

Try refreshing the page rapidly. Watch for:
- Captcha challenges
- 200 → 403 transition
- Redirects to `m.search.naver.com`

Document any observed protections.

- [ ] **Step 5: Save findings to `docs/superpowers/notes/naver-search-dom.md`**

Create file with the documented selectors, sample HTML snippets, and anti-bot notes. This file feeds the implementation in Task 2.

```markdown
# Naver Search Page DOM Reference (as of 2026-05-20)

## 서칭뷰 (SV) area

Container: `<exact-selector>`
Brand title: `<exact-selector>`
Link: `<exact-selector>` (attribute `href`)

Example HTML (anonymized):
```html
<paste actual snippet here>
```

## 신제품검색 (NP) area

(same fields)

## Anti-bot

(notes)
```

- [ ] **Step 6: Commit the notes**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git add docs/superpowers/notes/naver-search-dom.md
git commit -m "docs: Naver search DOM reference for brand scraper"
```

---

## Task 2: `naver_search.py` — Stage 1 (DOM scrape via browser-harness)

**Files:**
- Create: `worker/src/worker/lib/__init__.py` (empty)
- Create: `worker/src/worker/lib/naver_search.py`
- Modify: `worker/src/worker/models.py` (add `SlotExtract`)

- [ ] **Step 1: Add `SlotExtract` to `worker/src/worker/models.py`**

Append to the file:

```python
class SlotExtract(BaseModel):
    """A single ad slot extracted from a Naver search result page."""

    product: str  # "SEARCHING_VIEW" | "NEW_PRODUCT"
    slot_no: int  # 1 (서칭뷰) or 1/2 (신제품)
    display_name: str  # brand text as shown in the ad
    destination_url: str | None  # extracted href (may be Naver tracker URL)
```

- [ ] **Step 2: Create `worker/src/worker/lib/__init__.py`** (empty file)

- [ ] **Step 3: Write `worker/src/worker/lib/naver_search.py`**

The selectors in this template are **placeholders**. After Task 1, substitute the real selectors documented in `naver-search-dom.md`. Search the source for `# TODO[selector]` and replace.

```python
"""Stage 1: scrape brand display name + destination URL from Naver search results."""

from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent

from worker.logging import get_logger
from worker.models import SlotExtract

log = get_logger(__name__)


def scrape_brands_for_keyword(keyword: str) -> list[SlotExtract]:
    """Open Naver search, return all ad slots (SV + NP) for the given keyword.

    Uses browser-harness via subprocess so we don't compete with the user's
    interactive browser session. Each call gets its own short-lived session.
    """
    script = dedent(f"""
        new_tab("https://search.naver.com/search.naver?query={keyword}")
        wait_for_load()
        # Allow ad slots to hydrate
        import time; time.sleep(1.5)

        result = js(r'''
            const slots = [];

            // 서칭뷰 (1 slot expected)
            // TODO[selector] replace with real selector from naver-search-dom.md
            const svContainer = document.querySelector('div.sv_visual, [class*="searching_view"]');
            if (svContainer) {{
                const a = svContainer.querySelector('a[href]');
                const title = svContainer.querySelector('strong, .title, [class*="brand"]');
                slots.push({{
                    product: 'SEARCHING_VIEW',
                    slot_no: 1,
                    display_name: title ? title.textContent.trim() : '',
                    destination_url: a ? a.href : null,
                }});
            }}

            // 신제품검색 (up to 2 slots)
            // TODO[selector] replace with real selector
            const npSection = document.querySelector('section.np_visual, [class*="new_product"]');
            if (npSection) {{
                const cards = npSection.querySelectorAll('[class*="card"], [class*="item"]');
                cards.forEach((card, idx) => {{
                    if (idx > 1) return; // max 2 brands
                    const a = card.querySelector('a[href]');
                    const title = card.querySelector('strong, .title, [class*="brand"], [class*="name"]');
                    slots.push({{
                        product: 'NEW_PRODUCT',
                        slot_no: idx + 1,
                        display_name: title ? title.textContent.trim() : '',
                        destination_url: a ? a.href : null,
                    }});
                }});
            }}

            return JSON.stringify(slots);
        ''')

        print("RESULT_JSON_START")
        print(result)
        print("RESULT_JSON_END")
    """)

    proc = subprocess.run(
        ["browser-harness"],
        input=script,
        text=True,
        capture_output=True,
        timeout=60,
    )
    out = proc.stdout
    start = out.find("RESULT_JSON_START\n")
    end = out.find("\nRESULT_JSON_END")
    if start == -1 or end == -1:
        log.warning("no slots extracted", keyword=keyword, stderr=proc.stderr[:500])
        return []
    payload = out[start + len("RESULT_JSON_START\n") : end]

    import json

    try:
        raw_slots = json.loads(payload)
    except json.JSONDecodeError:
        log.exception("bad json from harness", payload=payload[:200])
        return []

    return [SlotExtract(**s) for s in raw_slots if s.get("display_name")]
```

⚠ This requires `browser-harness` to be on PATH. The user's CLAUDE.md confirms it is.

⚠ The selectors marked `# TODO[selector]` MUST be replaced after Task 1 produces concrete DOM information.

- [ ] **Step 4: Smoke-test the import**

```
cd worker
uv run python -c "from worker.lib.naver_search import scrape_brands_for_keyword; print('import ok')"
```

Expected: `import ok`.

⚠ Do NOT run the actual scraper yet — that requires the real selectors. Save smoke-testing for Task 5.

- [ ] **Step 5: Commit**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git add worker/src/worker/lib worker/src/worker/models.py
git commit -m "feat(worker): naver_search scraper skeleton (selectors pending)"
```

---

## Task 3: Apply real Naver selectors

**Files:**
- Modify: `worker/src/worker/lib/naver_search.py`

- [ ] **Step 1: Read `docs/superpowers/notes/naver-search-dom.md`** (from Task 1)

- [ ] **Step 2: Replace each `# TODO[selector]` line in `worker/src/worker/lib/naver_search.py`** with the actual selectors

- [ ] **Step 3: Live-test against one keyword**

```
cd worker
uv run python -c "
from worker.lib.naver_search import scrape_brands_for_keyword
from worker.logging import configure_logging
configure_logging()
slots = scrape_brands_for_keyword('실비보험')
for s in slots:
    print(f'{s.product} slot{s.slot_no}: {s.display_name} -> {s.destination_url}')
"
```

Expected: 1 line for SV (실비보험 has 1 SV slot). If output is empty, the selectors are wrong — go back to Task 1 step 2 and refine.

- [ ] **Step 4: Test against an NP keyword**

```
cd worker
uv run python -c "
from worker.lib.naver_search import scrape_brands_for_keyword
from worker.logging import configure_logging
configure_logging()
for s in scrape_brands_for_keyword('쇼파'):
    print(f'{s.product} slot{s.slot_no}: {s.display_name} -> {s.destination_url}')
"
```

Expected: up to 2 NP lines.

- [ ] **Step 5: Commit the real selectors**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git add worker/src/worker/lib/naver_search.py
git commit -m "feat(worker): apply real Naver search selectors"
```

---

## Task 4: `landing.py` — Stage 2 (footer 사업자등록상호 extraction, TDD)

**Files:**
- Create: `worker/src/worker/lib/landing.py`
- Create: `worker/tests/fixtures/landing/` (3 snapshot HTML files)
- Create: `worker/tests/test_landing.py`

- [ ] **Step 1: Capture 3 real landing-page footers as fixtures**

Use browser-harness or `curl` to fetch 3 representative landing pages (whatever Task 3 produced). Strip everything except the last `<footer>` section (or last 2000 bytes) for size. Save as:

- `worker/tests/fixtures/landing/samsungfire.html` — 삼성화재 footer with `상호 : 삼성화재해상보험(주)` or similar
- `worker/tests/fixtures/landing/casamia.html` — 까사미아 with `(주)신세계까사` or similar
- `worker/tests/fixtures/landing/minimal_footer.html` — a deliberately minimal footer with `사업자등록번호 123-45-67890` only and no name (negative case)

The exact content depends on what Task 3 surfaces. Use the actual HTML — don't fabricate. To save real pages, run:

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
mkdir -p worker/tests/fixtures/landing
uv run --project worker python -c "
import httpx
from pathlib import Path

urls = {
  'samsungfire.html': 'https://www.samsungfire.com/individual/',
  'casamia.html': 'https://www.casamia.co.kr/',
}
for name, url in urls.items():
    r = httpx.get(url, headers={'User-Agent': 'Mozilla/5.0'}, follow_redirects=True, timeout=15)
    # Take the last 4000 bytes — footer is always at the bottom
    tail = r.text[-4000:]
    Path(f'worker/tests/fixtures/landing/{name}').write_text(tail, encoding='utf-8')
    print(f'wrote {name}: {len(tail)} chars')
"
```

Then create `worker/tests/fixtures/landing/minimal_footer.html` manually:

```html
<footer>
  <div>사업자등록번호 123-45-67890</div>
  <div>주소: 서울시 강남구</div>
</footer>
```

- [ ] **Step 2: Write failing tests `worker/tests/test_landing.py`**

```python
from pathlib import Path

from worker.lib.landing import extract_business_name

FIXTURES = Path(__file__).parent / "fixtures" / "landing"


def test_extracts_samsungfire():
    html = (FIXTURES / "samsungfire.html").read_text(encoding="utf-8")
    name = extract_business_name(html)
    assert name is not None
    assert "삼성화재" in name


def test_extracts_casamia():
    html = (FIXTURES / "casamia.html").read_text(encoding="utf-8")
    name = extract_business_name(html)
    assert name is not None
    assert "까사미아" in name or "신세계" in name


def test_returns_none_for_footer_without_business_name():
    html = (FIXTURES / "minimal_footer.html").read_text(encoding="utf-8")
    name = extract_business_name(html)
    assert name is None
```

- [ ] **Step 3: Verify tests fail (ImportError)**

```
cd worker
uv run pytest tests/test_landing.py -v
```

- [ ] **Step 4: Implement `worker/src/worker/lib/landing.py`**

```python
"""Stage 2: extract 사업자등록상호 from landing-page HTML footers."""

from __future__ import annotations

import re
from typing import Iterable

from bs4 import BeautifulSoup

# Patterns ranked: first match wins.
# Each pattern captures the business name in group(1).
_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"상호\s*(?:명|:)?\s*[:：]\s*([^\n<,|]+?)(?=\s*(?:대표|사업자|주소|전화|TEL|$|<))"),
    re.compile(r"회사명\s*[:：]\s*([^\n<,|]+?)(?=\s*(?:대표|사업자|주소|전화|TEL|$|<))"),
    re.compile(r"법인명\s*[:：]\s*([^\n<,|]+?)(?=\s*(?:대표|사업자|주소|전화|TEL|$|<))"),
]


def _candidate_texts(html: str) -> Iterable[str]:
    """Yield text blocks likely to contain footer info."""
    soup = BeautifulSoup(html, "html.parser")
    # Footers first, then any element with class containing 'footer'.
    for el in soup.find_all("footer"):
        yield el.get_text(" ", strip=True)
    for el in soup.find_all(class_=re.compile(r"footer", re.IGNORECASE)):
        yield el.get_text(" ", strip=True)
    # As last resort, the entire body text trailing chunk.
    body = soup.find("body")
    if body:
        text = body.get_text(" ", strip=True)
        yield text[-3000:]


def extract_business_name(html: str) -> str | None:
    """Return the first 사업자등록상호 found in any footer-like region, or None."""
    for text in _candidate_texts(html):
        for pat in _PATTERNS:
            m = pat.search(text)
            if m:
                name = m.group(1).strip()
                # Strip trailing punctuation
                name = name.rstrip("·•-—()")
                if 2 <= len(name) <= 60:
                    return name
    return None
```

- [ ] **Step 5: Run tests**

```
cd worker
uv run pytest tests/test_landing.py -v
```

Expected: 3 passed. If `samsungfire` or `casamia` fail because the regex doesn't match real footer wording, **inspect the fixture HTML**, identify the exact pattern, and add it to `_PATTERNS`. Re-run until passing.

- [ ] **Step 6: Commit**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git add worker/src/worker/lib/landing.py worker/tests/fixtures/landing worker/tests/test_landing.py
git commit -m "feat(worker): footer 사업자등록상호 extractor (TDD)"
```

---

## Task 5: `brand_match.py` — fuzzy match + upsert (TDD)

**Files:**
- Create: `worker/src/worker/lib/brand_match.py`
- Create: `worker/tests/test_brand_match.py`

- [ ] **Step 1: Write failing tests `worker/tests/test_brand_match.py`**

```python
import pytest

from worker.lib.brand_match import upsert_brand

pytestmark = pytest.mark.db


def test_inserts_new_brand_when_no_match(db_conn):
    bid = upsert_brand(db_conn, business_name="(주)테스트브랜드", display_name="테스트")
    assert isinstance(bid, int)
    cur = db_conn.cursor()
    cur.execute("SELECT business_name, display_name FROM brands WHERE id = %s", (bid,))
    bn, dn = cur.fetchone()
    assert bn == "(주)테스트브랜드"
    assert dn == "테스트"


def test_matches_existing_brand_by_exact_business_name(db_conn):
    bid1 = upsert_brand(db_conn, business_name="(주)테스트브랜드", display_name="테스트")
    bid2 = upsert_brand(db_conn, business_name="(주)테스트브랜드", display_name="테스트 다이렉트")
    assert bid1 == bid2
    cur = db_conn.cursor()
    cur.execute("SELECT aliases FROM brands WHERE id = %s", (bid1,))
    aliases = cur.fetchone()[0]
    assert "테스트 다이렉트" in aliases


def test_fuzzy_matches_when_no_business_name_provided(db_conn):
    bid1 = upsert_brand(db_conn, business_name="(주)테스트브랜드", display_name="테스트")
    # Same display, no business name → should fuzzy-match
    bid2 = upsert_brand(db_conn, business_name=None, display_name="테스트")
    assert bid1 == bid2
```

- [ ] **Step 2: Verify failure**

```
cd worker
uv run pytest tests/test_brand_match.py -v -m db
```

- [ ] **Step 3: Implement `worker/src/worker/lib/brand_match.py`**

```python
"""Brand normalization: fuzzy match incoming brand text against existing rows."""

from __future__ import annotations

from psycopg import Connection
from rapidfuzz import fuzz, process

# Display-name similarity threshold (0..100). Above → treat as same brand.
_FUZZY_THRESHOLD = 92


def upsert_brand(
    conn: Connection,
    *,
    business_name: str | None,
    display_name: str,
) -> int:
    """Find or insert a brand row, returning its id.

    Match priority:
    1. Exact match on `business_name` (when provided).
    2. Fuzzy match on `display_name` against existing rows (rapidfuzz, threshold {_FUZZY_THRESHOLD}).
    3. Otherwise insert new row.

    When the input arrives at an existing brand by alternate display_name,
    that variant is appended to `aliases` (jsonb array).
    """
    if not display_name:
        raise ValueError("display_name required")

    with conn.cursor() as cur:
        # Step 1 — exact business_name lookup
        if business_name:
            cur.execute(
                "SELECT id, display_name, aliases FROM brands WHERE business_name = %s",
                (business_name,),
            )
            row = cur.fetchone()
            if row:
                bid, existing_display, aliases = row
                _maybe_append_alias(conn, bid, existing_display, aliases, display_name)
                return bid

        # Step 2 — fuzzy match by display_name
        cur.execute("SELECT id, display_name, aliases FROM brands")
        candidates = cur.fetchall()
        if candidates:
            choices = {row[0]: row[1] for row in candidates}
            best = process.extractOne(
                display_name, choices, scorer=fuzz.token_sort_ratio, score_cutoff=_FUZZY_THRESHOLD
            )
            if best is not None:
                _matched_display, score, bid = best
                row = next(r for r in candidates if r[0] == bid)
                _maybe_append_alias(conn, bid, row[1], row[2], display_name)
                return bid

        # Step 3 — insert
        # If business_name is missing, synthesize a placeholder so the
        # unique constraint on `business_name` is satisfied. Using the display
        # with a sentinel prefix prevents accidental collisions.
        effective_bn = business_name or f"__unverified__::{display_name}"
        cur.execute(
            """
            INSERT INTO brands (business_name, display_name, aliases)
            VALUES (%s, %s, '[]'::jsonb)
            ON CONFLICT (business_name) DO UPDATE SET display_name = EXCLUDED.display_name
            RETURNING id
            """,
            (effective_bn, display_name),
        )
        return cur.fetchone()[0]


def _maybe_append_alias(
    conn: Connection,
    brand_id: int,
    existing_display: str,
    current_aliases: list[str],
    incoming_display: str,
) -> None:
    if incoming_display == existing_display or incoming_display in (current_aliases or []):
        return
    new_aliases = list(current_aliases or []) + [incoming_display]
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE brands SET aliases = %s::jsonb WHERE id = %s",
            (_json_dumps(new_aliases), brand_id),
        )


def _json_dumps(value: list[str]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
```

- [ ] **Step 4: Run tests**

```
cd worker
uv run pytest tests/test_brand_match.py -v -m db
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git add worker/src/worker/lib/brand_match.py worker/tests/test_brand_match.py
git commit -m "feat(worker): brand fuzzy-match + upsert helper"
```

---

## Task 6: `brand_scrape.py` — JOB 3 orchestrator

**Files:**
- Create: `worker/src/worker/jobs/brand_scrape.py`
- Create: `worker/tests/test_brand_scrape_e2e.py`

- [ ] **Step 1: Write the failing e2e test `worker/tests/test_brand_scrape_e2e.py`**

```python
"""E2E test for brand_scrape. Mocks the network/scraper layers; tests
the orchestrator+DB integration only."""

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
def _two_active_round_kgs(db_conn):
    cur = db_conn.cursor()
    cur.execute("SELECT id FROM products WHERE code = 'SEARCHING_VIEW'")
    sv_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM products WHERE code = 'NEW_PRODUCT'")
    np_id = cur.fetchone()[0]

    _, lvl2 = upsert_category_pair(db_conn, "__bs_금융__", "__bs_금융상품__")
    sv_kg = upsert_keyword_group(db_conn, sv_id, lvl2, "__bs_실비__")
    np_kg = upsert_keyword_group(db_conn, np_id, lvl2, "__bs_쇼파__")

    # Active round = today is within period_start..period_end
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
                display_name="까사미아",
                destination_url="https://casamia.example/",
            ),
            SlotExtract(
                product="NEW_PRODUCT",
                slot_no=2,
                display_name="한샘",
                destination_url="https://hanssem.example/",
            ),
        ]
    return []


def _fake_business_name(url: str) -> str | None:
    return {
        "https://samsungfire.example/": "삼성화재해상보험(주)",
        "https://casamia.example/": "(주)신세계까사",
        "https://hanssem.example/": "(주)한샘",
    }.get(url)


def test_scrape_brands_populates_round_brands(db_conn, _two_active_round_kgs):
    with patch("worker.jobs.brand_scrape.scrape_brands_for_keyword", side_effect=_fake_scrape), \
         patch("worker.jobs.brand_scrape.fetch_business_name", side_effect=_fake_business_name):
        result = scrape_brands_for_active_rounds(db_conn)

    assert result["slots_inserted"] == 3
    assert result["keyword_groups_scraped"] == 2

    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT b.display_name, rb.slot_no, rb.source, rb.confidence
        FROM round_brands rb
        JOIN brands b ON b.id = rb.brand_id
        WHERE rb.round_keyword_group_id IN (%s, %s)
        ORDER BY rb.round_keyword_group_id, rb.slot_no
        """,
        (_two_active_round_kgs["sv_rkg"], _two_active_round_kgs["np_rkg"]),
    )
    rows = cur.fetchall()
    names = [r[0] for r in rows]
    assert "삼성화재" in names
    assert "까사미아" in names
    assert "한샘" in names
```

- [ ] **Step 2: Verify it fails**

```
cd worker
uv run pytest tests/test_brand_scrape_e2e.py -v -m db
```

- [ ] **Step 3: Implement `worker/src/worker/jobs/brand_scrape.py`**

```python
"""JOB 3: brand scraping orchestrator."""

from __future__ import annotations

import time
from datetime import date
from typing import Optional

import httpx
from psycopg import Connection

from worker.db import connect
from worker.lib.brand_match import upsert_brand
from worker.lib.landing import extract_business_name
from worker.lib.naver_search import scrape_brands_for_keyword
from worker.logging import configure_logging, get_logger
from worker.upsert import complete_ingest_run, fail_ingest_run, start_ingest_run

log = get_logger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_DELAY_SECONDS = 3.0  # Between Naver searches — anti-bot guard


def fetch_business_name(url: str) -> Optional[str]:
    """Stage 2 wrapper: GET the landing URL, extract 사업자등록상호 from footer."""
    try:
        with httpx.Client(
            headers={"User-Agent": _USER_AGENT}, timeout=15.0, follow_redirects=True
        ) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return None
            return extract_business_name(resp.text)
    except Exception:
        log.exception("landing fetch failed", url=url)
        return None


def scrape_brands_for_active_rounds(conn: Connection) -> dict[str, int]:
    """Find keyword groups in currently-active rounds and scrape brands for each."""
    today = date.today().isoformat()
    run_id = start_ingest_run(conn, run_type="brand_scrape")
    slots_inserted = 0
    kgs_scraped = 0

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT rkg.id, kg.name, p.code, p.max_brands_per_group
                FROM round_keyword_groups rkg
                JOIN rounds r ON r.id = rkg.round_id
                JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
                JOIN products p ON p.id = r.product_id
                WHERE r.period_start <= %s AND r.period_end >= %s
                """,
                (today, today),
            )
            rows = cur.fetchall()

        for rkg_id, kw, product_code, max_brands in rows:
            kgs_scraped += 1
            slots = scrape_brands_for_keyword(kw)
            slots = [s for s in slots if s.product == product_code][:max_brands]

            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM round_brands WHERE round_keyword_group_id = %s",
                    (rkg_id,),
                )

            if not slots:
                log.info("no slots", keyword=kw, product=product_code)
                time.sleep(_DELAY_SECONDS)
                continue

            for slot in slots:
                business_name = (
                    fetch_business_name(slot.destination_url)
                    if slot.destination_url
                    else None
                )
                confidence = 0.95 if business_name else 0.75
                source = "landing" if business_name else "dom"
                brand_id = upsert_brand(
                    conn,
                    business_name=business_name,
                    display_name=slot.display_name,
                )
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO round_brands (
                            round_keyword_group_id, brand_id, slot_no, source, confidence
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (round_keyword_group_id, slot_no)
                        DO UPDATE SET brand_id = EXCLUDED.brand_id,
                                      source = EXCLUDED.source,
                                      confidence = EXCLUDED.confidence,
                                      captured_at = now()
                        """,
                        (rkg_id, brand_id, slot.slot_no, source, confidence),
                    )
                slots_inserted += 1

            time.sleep(_DELAY_SECONDS)

        complete_ingest_run(
            conn, run_id=run_id, rows_total=kgs_scraped, rows_inserted=slots_inserted
        )
        return {"slots_inserted": slots_inserted, "keyword_groups_scraped": kgs_scraped}
    except Exception as exc:
        fail_ingest_run(conn, run_id=run_id, error_message=str(exc))
        raise


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    with connect() as conn:
        result = scrape_brands_for_active_rounds(conn)
        conn.commit()
        log.info("brand scrape done", **result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run e2e tests**

```
cd worker
uv run pytest tests/test_brand_scrape_e2e.py -v -m db
```

Expected: PASS.

- [ ] **Step 5: Full test sweep**

```
cd worker
uv run pytest -v
```

Expected: 26 tests pass (20 prior + 3 landing + 3 brand_match... actually count above: 3 brand_match + 3 landing + 1 e2e = 7, total 27).

- [ ] **Step 6: Commit**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git add worker/src/worker/jobs/brand_scrape.py worker/tests/test_brand_scrape_e2e.py
git commit -m "feat(worker): JOB 3 brand_scrape orchestrator (TDD)"
```

---

## Task 7: Live brand scrape on real active rounds

**Files:** (runtime task)

- [ ] **Step 1: Confirm there are active rounds**

```
cd worker
uv run python -c "
from datetime import date
import psycopg
from worker.config import load_settings
s = load_settings()
with psycopg.connect(s.database_url) as conn:
    cur = conn.cursor()
    cur.execute('''
        SELECT p.code, COUNT(DISTINCT r.id), COUNT(rkg.*)
        FROM rounds r
        JOIN products p ON p.id = r.product_id
        JOIN round_keyword_groups rkg ON rkg.round_id = r.id
        WHERE r.period_start <= %s AND r.period_end >= %s
        GROUP BY p.code
    ''', (date.today().isoformat(), date.today().isoformat()))
    for row in cur.fetchall(): print(row)
"
```

Expected: 2 rows (one per product). The "COUNT(rkg.*)" tells how many keyword groups will be scraped (potentially thousands for NP → expensive at 3s/each).

- [ ] **Step 2: Pilot run — 10 keyword groups only**

Add a `--limit N` flag to `brand_scrape.py` for the pilot. Modify the `scrape_brands_for_active_rounds` function to accept an optional `limit: int | None = None` and apply `LIMIT %s` in the SQL when set. Update `main()` to parse `--limit`.

Then:

```
cd worker
uv run python -m worker.jobs.brand_scrape --limit 10
```

Expected: about 30-60 seconds (10 kg × ~3-5s each). Slack-friendly log lines per kg.

⚠ Watch the output for any 403/captcha symptoms. If detected, STOP and report — we need to back off rate, refresh selectors, or invoke a different anti-bot mitigation.

- [ ] **Step 3: Spot-check `round_brands`**

```
cd worker
uv run python -c "
import psycopg
from worker.config import load_settings
s = load_settings()
with psycopg.connect(s.database_url) as conn:
    cur = conn.cursor()
    cur.execute('''
        SELECT rb.slot_no, b.display_name, b.business_name, rb.source, rb.confidence
        FROM round_brands rb
        JOIN brands b ON b.id = rb.brand_id
        ORDER BY rb.captured_at DESC
        LIMIT 20
    ''')
    for row in cur.fetchall(): print(row)
"
```

Expected: 10-20 rows with sensible names + ~70% with `source=landing`.

- [ ] **Step 4: Full run (NO limit) — only if pilot looks healthy**

```
cd worker
uv run python -m worker.jobs.brand_scrape
```

Expected duration: ~30 minutes for ~600 keyword groups (active rounds across both products) at 3s delay.

⚠ Run in the background and monitor for failures the same way W2 backfill did.

- [ ] **Step 5: Commit logs / summary**

Append to root `README.md`:

```markdown

### W4 brand scrape result (2026-05-21)

Scraped active-round keyword groups via Naver search:
- Keyword groups scraped: <N>
- Brand slots inserted: <N>
- Brands master: <N> unique 사업자등록상호
- `source=landing`: <N>%, `source=dom`: <N>%
```

Then:

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git add README.md
git commit -m "docs: log W4 brand scrape result"
```

---

# PHASE B — Display (Dashboard)

## Task 8: Extend types + queries with brand data

**Files:**
- Modify: `apps/dashboard/types/bid-decision.ts`
- Modify: `apps/dashboard/lib/db/queries.ts`

- [ ] **Step 1: Add brand fields to types**

Append/modify in `apps/dashboard/types/bid-decision.ts`:

```ts
export type RoundBrand = {
  slotNo: number;
  displayName: string;
  businessName: string;
  source: "dom" | "landing" | "manual" | "scrape_failed";
  confidence: number | null;
};

// Augment RoundRow:
```

Change existing `RoundRow` to include `brands`:

```ts
export type RoundRow = {
  roundId: number;
  roundNo: number;
  periodStart: string;
  periodEnd: string;
  minBidPrice: number | null;
  regularWinningBid: number | null;
  emptySlots: number | null;
  bidStatus: string | null;
  ratio: number | null;
  brands: RoundBrand[];          // NEW
};
```

And add to `KeywordGroupSummary`:

```ts
  latestBrands: RoundBrand[];    // NEW — brands on the most recent round
```

- [ ] **Step 2: Modify `getKeywordGroupSummary` in queries.ts**

After the existing tail query, add a brand fetch:

```ts
  const brandsResult = await db.execute<{
    round_id: number;
    slot_no: number;
    display_name: string;
    business_name: string;
    source: string;
    confidence: number | null;
  }>(sql`
    SELECT
      rkg.round_id,
      rb.slot_no,
      b.display_name,
      b.business_name,
      rb.source,
      rb.confidence
    FROM round_brands rb
    JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
    JOIN brands b ON b.id = rb.brand_id
    WHERE rkg.keyword_group_id = ${args.keywordGroupId}
    ORDER BY rb.slot_no
  `);
  const brandsByRound = new Map<number, RoundBrand[]>();
  for (const r of brandsResult.rows) {
    const list = brandsByRound.get(r.round_id) ?? [];
    list.push({
      slotNo: r.slot_no,
      displayName: r.display_name,
      businessName: r.business_name,
      source: r.source as RoundBrand["source"],
      confidence: r.confidence,
    });
    brandsByRound.set(r.round_id, list);
  }
```

Then in the `roundsAsc.map`, attach brands:

```ts
      brands: brandsByRound.get(r.round_id) ?? [],
```

Set `latestBrands` in the returned object:

```ts
    latestBrands: roundsAsc[roundsAsc.length - 1]?.brands ?? [],
```

(Add the import: `import type { RoundBrand } from "@/types/bid-decision";`)

- [ ] **Step 3: Type-check + build**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct/apps/dashboard"
pnpm exec tsc --noEmit 2>&1 | tail -10
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
pnpm --filter dashboard build 2>&1 | tail -5
```

Expected: 0 errors, build success.

- [ ] **Step 4: Commit**

```
git add apps/dashboard/types apps/dashboard/lib/db/queries.ts
git commit -m "feat(dashboard): expose brand data per round in queries"
```

---

## Task 9: Wire brands into Summary card, Round table, Trend chart

**Files:**
- Modify: `apps/dashboard/components/bid-decision/summary-card.tsx`
- Modify: `apps/dashboard/components/bid-decision/round-table.tsx`
- Modify: `apps/dashboard/components/bid-decision/trend-chart.tsx`

- [ ] **Step 1: Update `SummaryCard`**

Replace the `현재 집행 브랜드` Stat with:

```tsx
        <div>
          <div className="text-xs text-muted-foreground">현재 집행 브랜드</div>
          <div className="flex flex-wrap items-center gap-1.5">
            {summary.latestBrands.length === 0 ? (
              <span className="text-sm text-muted-foreground">- (집행사 없음 또는 미수집)</span>
            ) : (
              summary.latestBrands.map((b) => (
                <span
                  key={b.slotNo}
                  className="rounded-md border bg-muted/40 px-2 py-0.5 text-sm font-medium"
                  title={`${b.businessName} · ${b.source} · ${b.confidence ?? "-"}`}
                >
                  {b.displayName}
                </span>
              ))
            )}
          </div>
        </div>
```

(Replace the previous static `Stat label="현재 집행 브랜드" value="- (W4 예정)"` block.)

- [ ] **Step 2: Update `RoundTable`**

In the brand column, replace the static `- (W4)` with:

```tsx
              <TableCell className="text-xs">
                {r.brands.length === 0 ? (
                  <span className="text-muted-foreground">-</span>
                ) : (
                  r.brands
                    .map((b) => b.displayName)
                    .join(" / ")
                )}
              </TableCell>
```

- [ ] **Step 3: Update `TrendChart`**

Add brand info to the tooltip. Change the Tooltip element to a custom content renderer:

```tsx
import type { TooltipProps } from "recharts";

type ChartDatum = {
  round: string;
  minBid: number | null;
  winning: number | null;
  brands: string[];
};

function ChartTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload as ChartDatum;
  return (
    <div className="rounded-md border bg-background px-3 py-2 text-xs shadow">
      <div className="font-semibold">{label}</div>
      {payload.map((p) => (
        <div key={p.name}>
          {p.name}: {p.value == null ? "-" : `${Number(p.value).toLocaleString()}원`}
        </div>
      ))}
      {d.brands.length > 0 && (
        <div className="mt-1 border-t pt-1 text-muted-foreground">
          집행: {d.brands.join(" / ")}
        </div>
      )}
    </div>
  );
}
```

And in the LineChart, change `<Tooltip ... />` to `<Tooltip content={<ChartTooltip />} />` and update the `data` mapping to include brands:

```tsx
  const data: ChartDatum[] = rounds.map((r) => ({
    round: String(r.roundNo),
    minBid: r.minBidPrice,
    winning: r.regularWinningBid,
    brands: r.brands.map((b) => b.displayName),
  }));
```

- [ ] **Step 4: Build + visual check**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
pnpm --filter dashboard build 2>&1 | tail -5
```

Expected: build success.

Spot-check the dashboard live (next dev → http://localhost:3000). Pick a kg that has brands (likely one from `__bs_*` synthetic test data won't be there in real DB; use a real kg like 실비보험 after Task 7). Brand chips should appear in summary; brand names in table; brand list in chart tooltip.

- [ ] **Step 5: Commit**

```
git add apps/dashboard/components/bid-decision
git commit -m "feat(dashboard): show brand chips on Screen 1 (summary/table/tooltip)"
```

---

## Task 10: Screen 3 — `/brand` page (브랜드 점유)

**Files:**
- Create: `apps/dashboard/app/brand/page.tsx`
- Create: `apps/dashboard/components/brand/category-heatmap.tsx`
- Create: `apps/dashboard/components/brand/brand-table.tsx`

- [ ] **Step 1: Add a query for brand heatmap data**

Append to `apps/dashboard/lib/db/queries.ts`:

```ts
export type HeatmapRow = {
  brandId: number;
  displayName: string;
  roundNo: number;
  product: ProductCode;
  keywordGroupName: string;
  slotNo: number;
};

export async function getBrandHeatmap(args: {
  product: ProductCode;
  categoryLvl1: string | null;
  lastNRounds: number;
}) {
  const result = await db.execute<HeatmapRow & {
    brand_id: number;
    display_name: string;
    round_no: number;
    keyword_group_name: string;
    slot_no: number;
  }>(sql`
    SELECT
      b.id AS brand_id,
      b.display_name,
      r.round_no,
      p.code AS product,
      kg.name AS keyword_group_name,
      rb.slot_no
    FROM round_brands rb
    JOIN round_keyword_groups rkg ON rkg.id = rb.round_keyword_group_id
    JOIN rounds r ON r.id = rkg.round_id
    JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id
    JOIN categories c2 ON c2.id = kg.category_id
    JOIN categories c1 ON c1.id = c2.parent_id
    JOIN products p ON p.id = r.product_id
    JOIN brands b ON b.id = rb.brand_id
    WHERE p.code = ${args.product}
      ${args.categoryLvl1 ? sql`AND c1.name = ${args.categoryLvl1}` : sql``}
      AND r.round_no IN (
        SELECT DISTINCT round_no FROM rounds
        WHERE product_id = p.id
        ORDER BY round_no DESC
        LIMIT ${args.lastNRounds}
      )
    ORDER BY b.display_name, r.round_no DESC
  `);
  return result.rows.map((r) => ({
    brandId: r.brand_id,
    displayName: r.display_name,
    roundNo: r.round_no,
    product: r.product,
    keywordGroupName: r.keyword_group_name,
    slotNo: r.slot_no,
  }));
}
```

- [ ] **Step 2: Write `apps/dashboard/components/brand/category-heatmap.tsx`**

```tsx
import type { HeatmapRow } from "@/lib/db/queries";

export function CategoryHeatmap({ rows }: { rows: HeatmapRow[] }) {
  // Build matrix: brands rows × rounds cols
  const brands = Array.from(new Set(rows.map((r) => r.displayName))).sort();
  const roundNos = Array.from(new Set(rows.map((r) => r.roundNo))).sort((a, b) => a - b);
  const lookup = new Map<string, true>();
  for (const r of rows) lookup.set(`${r.displayName}|${r.roundNo}`, true);

  if (brands.length === 0) {
    return (
      <div className="rounded-md border bg-muted/30 p-8 text-center text-sm text-muted-foreground">
        해당 카테고리의 브랜드 데이터가 아직 없습니다.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="text-xs">
        <thead className="bg-muted/40">
          <tr>
            <th className="sticky left-0 bg-muted/40 px-3 py-2 text-left">브랜드</th>
            {roundNos.map((r) => (
              <th key={r} className="px-2 py-2 text-center font-mono">
                {r}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {brands.map((b) => (
            <tr key={b}>
              <td className="sticky left-0 bg-background px-3 py-1.5 font-medium">{b}</td>
              {roundNos.map((rn) => (
                <td key={rn} className="px-2 py-1.5 text-center">
                  {lookup.get(`${b}|${rn}`) ? (
                    <span className="inline-block h-2.5 w-2.5 rounded-sm bg-sky-500" />
                  ) : (
                    <span className="text-muted-foreground/40">─</span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Write `apps/dashboard/app/brand/page.tsx`**

```tsx
import { CategoryHeatmap } from "@/components/brand/category-heatmap";
import { getBrandHeatmap, getCategoriesLvl1, getProducts } from "@/lib/db/queries";
import type { ProductCode } from "@/types/bid-decision";

export const dynamic = "force-dynamic";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function pickStr(v: string | string[] | undefined): string | null {
  if (Array.isArray(v)) return v[0] ?? null;
  return v ?? null;
}

export default async function BrandPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const product = (pickStr(sp.product) as ProductCode | null) ?? "SEARCHING_VIEW";
  const cat1 = pickStr(sp.cat1);
  const lastN = Number(pickStr(sp.last) ?? 8);

  const [allProducts, lvl1, heatmap] = await Promise.all([
    getProducts(),
    getCategoriesLvl1(),
    getBrandHeatmap({ product, categoryLvl1: cat1, lastNRounds: lastN }),
  ]);

  return (
    <div>
      <header className="border-b px-6 py-3">
        <h1 className="text-lg font-semibold">브랜드 점유</h1>
        <p className="text-xs text-muted-foreground">
          카테고리 단위 회차별 집행 브랜드 변화를 확인합니다.
        </p>
      </header>

      <form
        method="GET"
        action="/brand"
        className="flex flex-wrap items-end gap-2 border-b bg-background/95 px-6 py-3 text-sm"
      >
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">제품</span>
          <select name="product" defaultValue={product} className={selectCls}>
            {allProducts.map((p) => (
              <option key={p.code} value={p.code}>{p.name}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">대분류</span>
          <select name="cat1" defaultValue={cat1 ?? ""} className={selectCls}>
            <option value="">(전체)</option>
            {lvl1.map((c) => (
              <option key={c.id} value={c.name}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-muted-foreground">기간</span>
          <select name="last" defaultValue={String(lastN)} className={selectCls}>
            {[6, 8, 12, 24].map((n) => (
              <option key={n} value={n}>최근 {n}회차</option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          className="ml-auto rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          적용
        </button>
      </form>

      <div className="space-y-4 px-6 py-4">
        <CategoryHeatmap rows={heatmap} />
      </div>
    </div>
  );
}

const selectCls =
  "rounded-md border border-input bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring";
```

- [ ] **Step 4: Build**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
pnpm --filter dashboard build 2>&1 | tail -5
```

Expected: build success, new route `/brand`.

- [ ] **Step 5: Live smoke test + screenshot**

```
pnpm --filter dashboard dev
```

Navigate to http://localhost:3000/brand → choose 대분류 → heatmap renders.

Capture screenshot to `docs/superpowers/screenshots/w4-screen3.png`.

- [ ] **Step 6: Commit**

```
git add apps/dashboard/app/brand apps/dashboard/components/brand apps/dashboard/lib/db/queries.ts docs/superpowers/screenshots
git commit -m "feat(dashboard): Screen 3 (브랜드 점유) with category heatmap"
```

---

## Task 11: Finalize — lint, full test, tag w4-complete

**Files:** (verification)

- [ ] **Step 1: Worker tests**

```
cd worker
uv run pytest -v
```

Expected: 27+ pass (20 from W2 + 3 landing + 3 brand_match + 1 brand scrape e2e).

- [ ] **Step 2: Lint**

```
cd worker
uv run ruff check .
uv run ruff format --check .
```

If format issues: `uv run ruff format .` and commit.

- [ ] **Step 3: Dashboard build**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
pnpm --filter dashboard build
```

Expected: clean build.

- [ ] **Step 4: Tag**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git tag w4-complete
git log --oneline w2-complete..HEAD
```

---

## W4 Acceptance Criteria

- [ ] `worker/tests` ≥ 27 passing
- [ ] `python -m worker.jobs.brand_scrape` runs end-to-end against real Naver and populates `round_brands`
- [ ] At least 50% of scraped brands have `source = "landing"` (footer matched)
- [ ] Screen 1: 실비보험 (or any active SV kg) shows brand chips in summary + table column + tooltip
- [ ] Screen 3: `/brand?product=SEARCHING_VIEW&cat1=금융` shows a category heatmap with brand rows × round columns
- [ ] `git tag w4-complete` exists

---

## Self-Review Notes

**Spec coverage:**
- §2.2 (brand scraping) — Tasks 2-6
- §3 (round_brands schema usage) — Tasks 5, 6, 8
- §4.1 JOB 3 — Task 6
- §5.3 Screen 3 — Task 10
- §5.5 brand display rules — Task 9 (서칭뷰=1 slot, 신제품=up to 2)

**Risks / known gaps:**
- Naver may update DOM (Task 1 selectors fragile) — mitigated by Task 1 explicit recon
- Some advertisers' footers won't match patterns — mitigated by `source` field distinguishing `landing` vs `dom` (DOM-only is acceptable; lower confidence)
- Captcha/throttle — `_DELAY_SECONDS = 3` is conservative; user can lower if observed safe
- Currently-active rounds query (`period_start <= today AND period_end >= today`) won't pick up rounds that are upcoming (입찰가능) — that's intentional; brands only exist for actively running rounds

**Deferred to W3 / W5:**
- NOSP auto-download (W3)
- Sheets sync of brand data (W5)
- Brand history line on TrendChart with marker shape per brand (visual polish, not data)

**Placeholder scan:** the `# TODO[selector]` markers in `naver_search.py` are intentional placeholders for Task 1's reconnaissance output. They are documented and explicitly part of Task 3's job to replace. Not a plan failure.
