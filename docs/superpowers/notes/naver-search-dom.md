# Naver Search Page DOM Reference (recon 2026-05-20)

Captured via Playwright MCP automation on real Naver search result pages.

## URL pattern

```
https://search.naver.com/search.naver?query=<keyword>
```

Renders both SV (서칭뷰) banner and NP (신제품검색 / "브랜드 콘텐츠") cards depending on which ads are running for the keyword.

## 서칭뷰 (SV)

- **Container**: `.searching_view`
- **Brand title + destination URL**: `.searching_view a.sub_title`
  - The anchor's `textContent` is the displayed campaign title (e.g., "삼성화재 다이렉트 실손의료비보험")
  - The anchor's `href` is a Naver tracker URL `https://ader.naver.com/v1/...` that 302-redirects to the advertiser's landing page

Sample DOM (from `?query=실비보험`):

```html
<div class="searching_view section brand_new_ui" data-collection="sc">
  <div class="section_head">
    <h2 class="blind">브랜드 검색</h2>
    <span class="icon_nad" aria-label="광고">…</span>
    <a class="sub_title" href="https://ader.naver.com/v1/…">
      <span>삼성화재 다이렉트 실손의료비보험</span>
    </a>
  </div>
  <div class="brand_wrap _brandad_video_container thumbnail_menu">…</div>
</div>
```

**Slot count**: 1 (matches spec — SV max 1 brand per keyword group).

The brand display name often includes a tagline ("삼성화재 다이렉트 실손의료비보험"). The advertiser is the leading brand word — for our purposes we keep the full string as `display_name` and rely on the landing-page footer for the canonical `business_name`.

## 신제품검색 (NP) — also rendered as "관련 브랜드 콘텐츠"

- **Section locator**: `div[class*="sc_new"]` whose first heading (h2/h3) `textContent` includes `브랜드 콘텐츠`
- **Cards**: `[class*="sds-comps-profile"][class*="type-basic"]` within that section
- **Brand title**: `[class*="profile-info-title"]` (e.g., "자코모", "도미실", "BASIC")
- **Card link**: each card has at least one `a[href*="ader.naver.com"]`; that's the destination URL

Sample (from `?query=쇼파`):

```
H2: "'쇼파' 관련 브랜드 콘텐츠"
- card 1: title="자코모"  link=https://ader.naver.com/v1/…(token A)
- card 2: title="도미실"  link=https://ader.naver.com/v1/…(token B)
- card 3: title="BASIC"   link=https://ader.naver.com/v1/…(token C)
```

**Slot count seen**: 3 visible. The user's product spec caps NP at 2 brand slots per keyword group, so the scraper should take `slots[:max_brands_per_group]`. (The 3rd card may be organic placement or paid; treating it conservatively as out-of-scope is safe.)

## Notes / gotchas

1. **CSS module hashing**: many sub-elements use generated class names like `anKY9lFJTqS_ed2kHN6S`. Don't rely on those. Stable hooks are: prefix-substring matches like `sds-comps-profile`, semantic class fragments (`profile-info-title`), heading text content (`"브랜드 콘텐츠"`), and known stable containers (`.searching_view`).
2. **Destination URLs** are always Naver tracker links (`https://ader.naver.com/v1/<token>`). To get the advertiser's actual domain, follow the 302 redirect. `httpx.get(url, follow_redirects=True)` works.
3. **No captcha** observed on direct navigation. Tested keywords: `실비보험`, `쇼파`. We'll keep a 3-second delay between scrapes to be safe.
4. **Mobile vs desktop**: tests above were on desktop UA. Mobile variant uses different selectors — keep User-Agent set to a desktop Chrome string.
5. **Hydration**: the SV banner and NP cards both render server-side enough that `wait_for_load()` suffices. No JS-driven async loading observed.
6. **0 brands case**: if `.searching_view` is absent and no `브랜드 콘텐츠` heading is found, the keyword has no SV/NP ads currently running. Return empty slot list.

## Selector summary (for naver_search.py)

```python
SV_CONTAINER = ".searching_view"
SV_TITLE_AND_LINK = ".searching_view a.sub_title"   # textContent + href

NP_SECTION_PROBE = 'div[class*="sc_new"]'
NP_SECTION_HEADING_MATCH = "브랜드 콘텐츠"             # textContent contains
NP_CARD = '[class*="sds-comps-profile"][class*="type-basic"]'
NP_CARD_TITLE = '[class*="profile-info-title"]'      # textContent
NP_CARD_LINK = 'a[href*="ader.naver.com"]'           # href, within card or its parent
```
