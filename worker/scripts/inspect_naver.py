"""Inspect actual Naver search DOM for SV/NP ad slots — debugging the scraper."""
from playwright.sync_api import sync_playwright

KEYWORDS = ["실비보험", "소파", "선글라스", "탈모"]
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

INSPECT_JS = r"""
() => {
  const out = {};

  // 1. SV section
  const sv = document.querySelector('.searching_view');
  if (sv) {
    out.sv_outer = sv.outerHTML.slice(0, 4000);
    const sub = sv.querySelector('a.sub_title');
    if (sub) {
      out.sv_sub_title_text = sub.textContent.trim();
      out.sv_sub_title_href = sub.href;
    }
    // Look for nearby brand-name-like elements
    const titles = sv.querySelectorAll('[class*="title"], [class*="brand"], [class*="name"], a, h2, h3, strong');
    out.sv_candidates = Array.from(titles).slice(0, 30).map(el => ({
      tag: el.tagName,
      cls: el.className,
      text: (el.textContent || '').trim().slice(0, 80),
      href: el.href || null,
    }));
  } else {
    out.sv = 'NOT FOUND (.searching_view)';
    // Try alternate class names
    const alt = document.querySelectorAll('[class*="searching"], [class*="search_view"], [class*="sa_brand"]');
    out.sv_alt = Array.from(alt).slice(0, 10).map(el => ({
      tag: el.tagName, cls: el.className, text: (el.textContent || '').trim().slice(0, 100)
    }));
  }

  // 2. NP section — look for "브랜드 콘텐츠" heading
  const sections = document.querySelectorAll('div[class*="sc_new"], section, div[class*="sc_"]');
  const npHits = [];
  for (const s of sections) {
    const h = s.querySelector('h2, h3, [class*="title"]');
    if (h && h.textContent && h.textContent.includes('브랜드 콘텐츠')) {
      npHits.push({
        cls: s.className,
        h_text: h.textContent.trim().slice(0, 100),
        outer: s.outerHTML.slice(0, 4000),
      });
    }
  }
  out.np_brand_sections = npHits;

  // Also search anywhere for "브랜드 콘텐츠" text
  out.brand_text_count = (document.body.innerText.match(/브랜드 콘텐츠/g) || []).length;

  return out;
};
"""

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(user_agent=UA, locale="ko-KR")
    page = ctx.new_page()
    for kw in KEYWORDS:
        url = f"https://search.naver.com/search.naver?query={kw}"
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)
        data = page.evaluate(INSPECT_JS)
        print(f"\n========== KEYWORD: {kw} ==========")
        import json
        # Print summary
        if 'sv_sub_title_text' in data:
            print(f"SV a.sub_title text: {data['sv_sub_title_text']!r}")
            print(f"SV a.sub_title href: {data.get('sv_sub_title_href')!r}")
        else:
            print(f"SV: {data.get('sv', 'present but no sub_title')}")
            print(f"SV alt elements: {data.get('sv_alt', [])[:3]}")
        if data.get('sv_candidates'):
            print("SV candidate elements:")
            for c in data['sv_candidates'][:10]:
                print(f"  {c['tag']} cls={c['cls'][:50]} text={c['text']!r}")
        print(f"NP '브랜드 콘텐츠' text appearances: {data['brand_text_count']}")
        print(f"NP brand sections found: {len(data['np_brand_sections'])}")
        for i, s in enumerate(data['np_brand_sections']):
            print(f"  [{i}] class={s['cls'][:80]}")
            print(f"      heading={s['h_text']!r}")
            print(f"      outer[:1500]={s['outer'][:1500]}")
    ctx.close()
    browser.close()
