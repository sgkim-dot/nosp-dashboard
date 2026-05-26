"""Test landing page biz-name extraction for a real ader.naver.com URL."""
import httpx
from worker.lib.landing import extract_business_name, _PATTERNS

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# A real ader URL from the inspect run (실비보험 SV ad → 삼성화재)
TEST_URLS = [
    # From previous SV scrape (실비보험)
    "https://ader.naver.com/v1/MGBJvQg5hnLEtRtocCmSurH1NB3kjNLOsFtGPnhGvjoN3knOBNZUB8FToyA8Qt-RlrkDZn7RtDhFXorOjnS4rBU5sSfsPAuI4A563I1BLo-BbgeB0-LNoThtCVS6iwY-ai0vd7ex-x9pIblw44lgrTqnV7eurDkRJXlb9Rkq_WtBUsaWBGngf1A1HB9Pa2EnGLzN7ES9bbYDfsolpE9KG339vxSyQQogIcy5UIqMxvmQ7uLStNvqrPPdK1rNAgJF3b15EOZYQp4VVPt4RJHBn_I4nm6gIaUytdh6mVCzx1xSULIH2t5-V2-h5pUiNhWKRxDgaBVgar561pwES8Glwz5aXgQ75yelsngwXL9j06kTyfGOxFsc9Gh0qUDyCiZBSWAoB1y2nUtoizfA7rdZjdVwqm3OmAM66YAfWprWqcVlfa-O19qYtbgNnLMQaec7QmKiKln68uvQd7q9rcWG9bCHUVYAQLnGuFe0q8uZbrhjs3cDqoT8BX-PXgEgXo4nJ9sat1UG9Z4fr32g0Oh6QfmIny8rVm1rgB3h5Hh-8C8=?c=naver.search.pc.sv&t=0",
]

def test_one(url: str):
    print(f"\n=== URL: {url[:100]}... ===")
    try:
        with httpx.Client(headers={"User-Agent": UA}, timeout=20.0, follow_redirects=True) as c:
            resp = c.get(url)
            print(f"Status: {resp.status_code}")
            print(f"Final URL: {str(resp.url)[:200]}")
            print(f"HTML length: {len(resp.text)}")
            # Search for biz-related strings
            html = resp.text
            for marker in ["상호", "사업자", "회사명", "법인명"]:
                if marker in html:
                    idx = html.find(marker)
                    print(f"  '{marker}' found at pos {idx}, context: {html[max(0,idx-50):idx+100]!r}")
            biz = extract_business_name(html)
            print(f"Extracted biz: {biz!r}")
            # Print last 2000 chars (likely footer area)
            print(f"\n--- LAST 2000 chars ---\n{html[-2000:]}")
    except Exception as e:
        print(f"ERROR: {e!r}")


if __name__ == "__main__":
    for u in TEST_URLS:
        test_one(u)
