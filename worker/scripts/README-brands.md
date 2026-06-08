# 브랜드 매핑 운영 가이드

브랜드 정리 페이지(`/brand-cleanup`)에 같은 사례가 자꾸 나타나는 문제의
**근본 원인 + 재발 방지 체계**.

## 동작 흐름 (어디서 어떻게 매핑되는지)

```
Naver 검색 결과 광고
    │
    ▼
naver_search.scrape_brands_for_keyword()   # Stage 1: 광고카피·URL 수집
    │
    ▼
brand_scrape.fetch_business_name(url)      # Stage 2: 호스트 해석
    │  (오직 다음 중 하나만 반환)
    │   - normalize_host(host)             ex. "shop.ivenet.co.kr"
    │   - platform_business_name(...)      ex. "brand.naver.com/lactiv"
    │   - None                             (해석 실패 시)
    ▼
brand_match.upsert_brand(business_name, display_name)
    │  [L1 가드] business_name이 한글/괄호/주식회사 등 junk면 None으로 강제
    │
    ▼
canonical_brand.canonical_brand_name(host, display)
    │  ① HOST_TO_BRAND[host]                          (가장 강함)
    │  ② Naver 플랫폼 path 슬러그                       (brand.naver.com/X → X)
    │  ③ DISPLAY_CANONICAL[display first word]         (잘못된 휴리스틱 교정)
    │  ④ guess_from_display (첫 단어 휴리스틱)
    │
    ▼  [L1.5 가드] canonical 잡혔는데 host 없으면
    ▼  HOST_TO_BRAND reverse → 대표 정규 호스트로 강제 점프
    ▼  (광고 카피 변형으로 __unverified__:: 행이 늘어나는 것 방지)
    ▼
brands 테이블에 INSERT/UPDATE
```

## 6중 방어 (재발 방지 체계)

| 계층 | 위치 | 방어 내용 |
|------|------|-----------|
| **L1** | `lib/brand_match.py::_is_junk_host` | 한글/괄호/주식회사 등이 들어간 `business_name`을 None으로 강제 → `__unverified__::` 센티넬로 fallback |
| **L1.5** | `lib/brand_match.py::_representative_host` | canonical은 알아냈는데 host가 None인 경우, HOST_TO_BRAND를 리버스 룩업해서 대표 정규 호스트로 자동 점프. 광고 카피 변형(예: "뻬를리 워치", "뻬를리 펜던트")이 각자 `__unverified__::` 행을 만드는 것을 방지 |
| **L2** | `jobs/brand_scrape.py::fetch_business_name` | `extract_business_name(resp.text)` 호출 제거. 페이지 footer의 한글 사명을 절대 host 컬럼에 저장하지 않음 |
| **L3** | `lib/canonical_brand.py::DISPLAY_CANONICAL` | 알려진 잘못된 첫 단어(Pro+, Qrevo, 뻬를리, 강력한, 에스클래스, …)는 정규명으로 강제 매핑 |
| **L4** | `scripts/reconcile_brands.py` | 매핑 추가 후 1커맨드로 (Step 0 junk bn 이전, Step 1 display backfill, Step 2 중복 행 병합, Step 3 JSON dump) 일괄 정리 |
| **L4.5** | `브랜드크롤링.bat` | 크롤링 끝나면 reconcile을 자동 호출. 사용자가 잊어도 안전 |
| **L5** | 이 문서 | 운영 워크플로 명문화 |

## 새 브랜드를 추가할 때 — 운영 워크플로

### 1단계. HOST_TO_BRAND 또는 DISPLAY_CANONICAL 수정

`worker/src/worker/lib/canonical_brand.py`를 직접 편집.

| 케이스 | 어디에 추가 |
|--------|-------------|
| URL 호스트로 브랜드 식별 가능 | `HOST_TO_BRAND` 에 `"hostname": "정규명"` 추가. www/m 변형도 함께 |
| 호스트 해석은 안 되는데 광고카피 첫 단어가 잘못 나오는 경우 | `DISPLAY_CANONICAL` 에 `"잘못된단어": "정규명"` 추가 |

### 2단계. reconcile 실행 (필수)

```powershell
cd worker
uv run python scripts/reconcile_brands.py            # dry-run으로 변경사항 확인
uv run python scripts/reconcile_brands.py --apply    # 적용
```

이 한 커맨드가 자동으로:
- Step 0: junk business_name 행을 깨끗한 호스트로 이전
- Step 1: 모든 brand 행의 display_name을 현재 매핑으로 재계산
- Step 2: 같은 정규명을 가진 중복 행 병합 (round_brands 재연결 포함)
- Step 3: 대시보드용 `apps/dashboard/lib/canonical-hosts.json` 재생성

### 3단계. (코드 수정한 경우만) 브랜드 크롤링 재시작

`canonical_brand.py` 만 수정한 경우 — DB는 reconcile로 갱신되므로 끝.

`brand_scrape.py` 나 `brand_match.py` 같은 **코드 자체**를 수정한 경우:
실행 중인 `브랜드크롤링.bat`을 **반드시 재시작**해야 새 코드가 적용됨.
Python 프로세스는 한번 로드한 모듈을 메모리에 캐싱하므로 .py 파일만
바꾸면 재시작 전까지 옛 코드를 그대로 사용함.

## 진단 도구

| 스크립트 | 용도 |
|----------|------|
| `scripts/diag_brand_hosts.py` | 특정 (host, expected canonical) 쌍이 DB에서 어떻게 매핑되어 있는지 검사. 사용자가 보고한 케이스를 빠르게 확인 |
| `scripts/trace_korean_brand_rows.py` | 한글/__unverified__ 형태의 business_name 행을 최근 생성순으로 나열 — 재발 모니터링용 |
| `scripts/check_ivenet.py` | 단일 브랜드의 DB 상태를 빠르게 확인 (템플릿) |

## 자주 묻는 트러블슈팅

### Q. 매핑을 추가했는데 대시보드에서 그대로 잘못된 이름이 보임
**원인**: reconcile를 안 돌렸거나, 또는 BAT 프로세스가 옛 코드를 사용 중.

**해결**: 위 2단계(reconcile)를 실행. 코드 수정이 있었다면 3단계(BAT 재시작)도.

### Q. 새로 크롤한 광고가 또 한글 사명 행을 만듦
**원인**: BAT 프로세스가 L1 가드 적용 전의 코드를 사용 중.

**해결**: BAT 종료 후 재실행. 새 프로세스는 `_is_junk_host` 가드로 한글 host를 차단.

### Q. 같은 정규명에 여러 행이 또 생김
**원인**: 새 호스트 변형(예: `www.X` vs `X`)이 들어왔는데 reconcile를 안 돌림.

**해결**: reconcile Step 2가 같은 canonical을 가진 행들을 자동 병합. 그냥 reconcile 한번 더.
