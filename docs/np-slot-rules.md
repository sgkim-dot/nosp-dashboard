# 신제품검색(NP) 슬롯 판정 룰

> 작성일: 2026-05-27
>
> 모바일 네이버 검색의 신제품검색(NP) 광고 슬롯을 정확히 식별하기 위한 규약.

## 1. 배경

NP는 모바일 전용 광고 상품으로, 한 키워드그룹(KG)에 **최대 2슬롯**을 운영합니다. 각 슬롯은 독립적인 입찰로 광고주가 결정됩니다.

네이버 모바일 검색 결과 페이지에서는 NP 광고가 **`<div class="api_subject_bx brand_wrap new_product_wrap">`** 영역에 렌더링되며, 내부 `.flick_container` 안에 `.flick_item` 요소들이 carousel 형태로 표시됩니다.

## 2. 핵심 관찰 (DOM 구조)

| 케이스 | flick_item 수 (단일 fetch) | unique ad_id 수 (단일 fetch) | 실제 슬롯 수 |
|--------|---------------------------|-----------------------------|--------------|
| 0슬롯 (광고 없음) | 0 (NP 섹션 미노출) 또는 1 (빈 placeholder, ad_id 없음) | 0 | **0** |
| 1슬롯 (한 광고주 1슬롯) | **1** | **1** | **1** |
| 2슬롯 (광고주 2명 또는 같은 광고주 2슬롯) | **4** (carousel × 2반복) | **2** | **2** |

각 `flick_item` 내부에는 `a[href*="ader.naver.com"]` 링크가 있고, `onclick="...i=SC*****..."` 의 `SC*` 부분이 ad_id(광고 placement 식별자)입니다.

## 3. 슬롯 판정 알고리즘

### 3.1 단일 fetch 기반 슬롯 카운트

```
slot_count_in_fetch = (flick_item 안에서 추출한 unique ad_id 수)
```

### 3.2 회전(rotation) 대응 — 5회 fetch 후 host 기준 dedup

네이버는 같은 광고주에게도 fetch마다 **다른 ad_id**를 부여하기도 하고 (rotation), 한 fetch에서는 광고를 표시하지 않기도 합니다(빈 슬롯 충전 효과).

따라서:

1. **5회 fetch 수행**, 각 fetch에서 ad_id + 광고 카피 + destination_url 수집 후 union
2. 각 ad_id의 `destination_url` (ader.naver.com) 을 `httpx`로 따라가서 **최종 hostname** 추출 (`*.brand.naver.com/{slug}` 같은 플랫폼은 path 1단계까지 포함)
3. **hostname 기준 dedup** — 같은 host의 여러 ad_id는 1슬롯
4. 결과: `slot_count = unique advertiser hostname 수`

### 3.3 정합성 룰

- 같은 `hostname` → **같은 슬롯** (회전으로 ad_id가 바뀌어도 1슬롯)
- 다른 `hostname` → **별개 슬롯** (캐노니컬 브랜드명이 같아도 분리 저장)

이는 한 광고주가 여러 도메인을 통해 입찰한 경우를 정확히 반영하기 위함입니다. 예를 들어 라이나생명은 `mdirect.lina.co.kr` 과 `mdirect.e-lina.co.kr` 두 도메인으로 2슬롯을 점유할 수 있습니다.

## 4. 검증된 케이스

### 4.1 1슬롯 케이스 — 칫솔 (NP)
- 광고주: 왕타 (1개)
- DOM: 매 fetch마다 `flick_item=1` 또는 NP 섹션 미노출(rotation)
- ad_id: fetch마다 다른 `SC*` 부여되지만 모두 `brand.naver.com/wangta` 로 redirect
- **저장**: round_brands 1행 (slot_no=1, brand=왕타, host=brand.naver.com/wangta)

### 4.2 2슬롯 케이스 (같은 광고주) — 어린이치아보험 (NP)
- 광고주: 라이나생명 (1개 캐노니컬 브랜드, 2개 host)
- DOM: 매 fetch마다 `flick_item=4`, `unique ad_id=2`
- ad_id 호스트:
  - `SC3892960` → `mdirect.e-lina.co.kr`
  - `SC3896390` → `mdirect.lina.co.kr`
  - `SC3900066` → `mdirect.e-lina.co.kr` (회전 시 SC 재발급)
- **저장**: round_brands 2행 (slot 1 = `mdirect.lina.co.kr`, slot 2 = `mdirect.e-lina.co.kr`, 둘 다 캐노니컬 "라이나생명")

### 4.3 1슬롯 케이스 — 운전자보험 (NP)
- 광고주: 삼성화재
- DOM: `flick_item=1`, `unique ad_id=1`
- **저장**: round_brands 1행 (slot_no=1, brand=삼성화재, host=direct.samsungfire.com)

## 5. 구현 참조

| 항목 | 위치 |
|------|------|
| 5회 fetch + ad_id union | `worker/src/worker/lib/naver_search.py` (`_NP_RETRIES = 5`) |
| destination_url → hostname 해석 | `worker/src/worker/jobs/brand_scrape.py::fetch_business_name` |
| host 기준 dedup | `worker/src/worker/jobs/brand_scrape.py` 의 scrape loop |
| 호스트 → 캐노니컬 브랜드명 매핑 | `worker/src/worker/lib/canonical_brand.py::HOST_TO_BRAND` |

## 6. 향후 적용 원칙

- 모든 신규 캡쳐는 본 규약을 자동 따름
- 기존 데이터는 `dedupe_existing_slots.py` 로 host 기준 dedup 완료
- DOM 구조 변경 (Naver UI 업데이트) 시 본 문서 + 스크래퍼 코드 동시 갱신 필요

## 7. NOSP `empty_slots` 와의 관계

NOSP CSV의 `현재공실구좌` 컬럼은 **남은 빈 슬롯 수**를 의미합니다.

- `empty_slots=0` → 두 슬롯 모두 입찰 완료 (한 광고주가 2슬롯을 점유했을 수도, 두 광고주가 1슬롯씩 점유했을 수도 있음)
- `empty_slots=1` → 한 슬롯만 점유, 다른 한 슬롯 비어있음
- `empty_slots=2` → 두 슬롯 모두 비어있음 (광고 없음)

스크래퍼 결과의 슬롯 수가 `2 - empty_slots` 와 일치해야 정상. 일치하지 않으면:
- 스크래퍼 수가 적음 → fetch 중 광고 회전으로 일부 슬롯 못 잡음 (재실행 권장)
- 스크래퍼 수가 많음 → host 기준 dedup이 정상 동작하지 않은 경우 (코드 검토 필요)
