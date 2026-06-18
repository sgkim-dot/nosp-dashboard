# Naver 광고 캐러셀 — Dot indicator 패턴

## 핵심 사실

Naver 검색 결과 광고 카드 하단에 작은 점들(pagination dots)이 표시된다.
**점의 개수 = 그 회차에 운영 중인 광고 슬롯 수**

| dot 수 | 의미 |
|--------|------|
| 점 없음 | 단일 광고 (캐러셀 없음) |
| 1개 | 1 슬롯 운영 (광고주 1개) |
| 2개 | 2 슬롯 운영 (광고주 2개, 회전 노출) |

이는 NOSP CSV의 `total_slots` 컬럼과 동일한 정보. NOSP가 정확하면 이 두 값이 일치해야 한다.

## brand_scrape 누락 진단

`brand_scrape` (worker/jobs/brand_scrape.py)이 `naver_search.scrape_brands_for_keyword()`로 NP는 모바일 검색을 5번 fetch + 결과 union으로 광고를 잡는다. 그래도 광고 회전으로 가끔 누락된다.

**누락 판단 기준**:
- 잡힌 광고 수 < 검색 결과의 dot indicator 개수 → 누락
- 또는 NOSP CSV의 `total_slots` > 우리가 잡은 round_brands 수 → 누락

## 발견 시 대응

### 즉시 — 단일 KG 강제 재스크랩

```python
# worker/scripts/rescrape_silbi.py 참고
from worker.db import connect
from worker.jobs.brand_scrape import scrape_brands_for_active_rounds

with connect() as conn:
    scrape_brands_for_active_rounds(conn, rkg_ids=[<RKG_ID>])
```

또는 brand_scrape 모듈을 CLI에서 호출할 때 `rkg_ids` 옵션을 노출하도록 개선하면
`uv run python -m worker.jobs.brand_scrape --rkg-id 307321` 같이 사용 가능.

### 다음 회차 — 자동 보정

다음 BAT 실행 시 `--resume`이 24h 이상 된 KG를 자동 처리. 새 회차에서 광고가 다시
보이면 정상 채워짐. 광고가 계속 안 보이면 진짜 누락.

## 향후 코드 개선 (미구현 백로그)

1. **`_EXTRACT_JS` (naver_search.py)에 dot indicator 추출 추가**
   - 페이지 DOM에서 광고 캐러셀 하단의 pagination dots count 가져오기
   - SlotExtract에 `detected_slot_count: int` 필드 추가
2. **brand_scrape이 detected_slot_count > found_slots면 재시도**
   - 현재는 5번 fetch 후 0건이면 1번 더 retry. dot 기준으로 조건부 추가 retry 가능
3. **round_keyword_groups에 `detected_slot_count` 저장**
   - 대시보드 cleanup 페이지에서 "NOSP는 N슬롯인데 우리는 M(<N)건만 잡음" KG 알람
   - 운영자가 manual 재스크랩 또는 매핑 추가 결정

## 관련 사례

- **2026-06-18 NP r202625 실비보험**: NOSP `total_slots=2`, 어제 23:33 스크랩 0건. 모바일 검색에 KB 광고 + dot 2개 → 누락 확인. 강제 재스크랩으로 KB 1건 잡음. 두 번째 광고주는 다음 회차 대기.
