"""Inspect mobile Naver search for actual NP (신제품검색) ad slots.

NP is mobile-only. PC desktop search.naver.com does NOT contain real NP ads.
Mobile: m.search.naver.com
"""
from playwright.sync_api import sync_playwright

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

INSPECT_JS = r"""
() => {
  const out = {};

  // Strategy: dump every visible section's heading + first few text/links
  const sections = document.querySelectorAll('section, div[class*="sc_"], div[class*="api_"], div[class*="sp_"], div[id*="main"] > div');
  const sectionInfo = [];
  for (const s of sections) {
    const heading = s.querySelector('h2, h3, [class*="title"], [class*="header"]');
    const head_text = heading ? (heading.textContent || '').trim().slice(0, 60) : '';
    if (!head_text) continue;
    const anchors = s.querySelectorAll('a');
    const sample_links = Array.from(anchors).slice(0, 6).map(a => ({
      text: (a.textContent || '').trim().slice(0, 60),
      href: (a.href || '').slice(0, 80),
    }));
    const has_ader = Array.from(anchors).some(a => (a.href || '').includes('ader.naver.com'));
    sectionInfo.push({
      head_text,
      cls: s.className.slice(0, 80),
      ader_links: has_ader,
      sample_links: sample_links.filter(l => l.text || l.href),
    });
  }
  out.sections = sectionInfo;

  // Search for any element near 신제품 / 광고 markers
  out.has_text_npview = document.body.innerText.includes('파워컨텐츠') ||
                       document.body.innerText.includes('PowerContents') ||
                       document.body.innerText.includes('파워콘텐츠');
  // Look for the ader.naver.com links count
  out.ader_link_count = document.querySelectorAll('a[href*="ader.naver.com"]').length;
  // First 5 ader links with their parent section info
  const aders = document.querySelectorAll('a[href*="ader.naver.com"]');
  out.aders_sample = Array.from(aders).slice(0, 10).map(a => {
    let p = a.parentElement;
    let path = '';
    for (let i = 0; i < 4 && p; i++) {
      path += (p.tagName + '.' + (p.className || '').slice(0, 40) + ' > ');
      p = p.parentElement;
    }
    return {
      text: (a.textContent || '').trim().slice(0, 80),
      href: a.href.slice(0, 100),
      parent_path: path,
    };
  });
  return out;
};
"""


def run_one(kw: str):
    url = f"https://m.search.naver.com/search.naver?query={kw}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=MOBILE_UA,
            locale="ko-KR",
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
        )
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(3000)
        # Scroll a bit to trigger lazy load
        page.evaluate("window.scrollBy(0, 800)")
        page.wait_for_timeout(1500)
        page.evaluate("window.scrollBy(0, 800)")
        page.wait_for_timeout(1500)
        data = page.evaluate(INSPECT_JS)
        print(f"\n========== MOBILE: {kw} ==========")
        print(f"URL: {url}")
        print(f"ader_link_count: {data['ader_link_count']}")
        print(f"has_text_npview: {data['has_text_npview']}")
        print("\n--- Sections with headings ---")
        for s in data["sections"]:
            tag = " [AD]" if s["ader_links"] else ""
            print(f"  [{s['head_text']}]{tag}")
            print(f"    cls={s['cls']}")
            for l in s["sample_links"]:
                print(f"    - {l['text']!r} -> {l['href']}")
        print("\n--- ader.naver.com links (first 10) ---")
        for a in data.get("aders_sample", []):
            print(f"  text={a['text']!r}")
            print(f"    href={a['href']}")
            print(f"    parent_path={a['parent_path']}")
        ctx.close()
        browser.close()


if __name__ == "__main__":
    for kw in ["운전자보험", "실비보험", "소파"]:
        run_one(kw)
