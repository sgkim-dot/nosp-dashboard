# NOSP 입찰·낙찰가 대시보드 설계

- **일자**: 2026-05-19
- **상태**: Draft (사용자 리뷰 대기)
- **범위**: 네이버 서칭뷰 / 신제품검색 회차·키워드그룹별 최저입찰가·낙찰가·집행 브랜드를 통합 관리하는 DB 기반 대시보드

---

## 1. 목적과 페이즈 구분

전사 공유를 전제로, 회차마다 갱신되는 입찰 데이터와 경쟁 브랜드 동향을 한 곳에서 누적·조회·의사결정에 사용한다.

- **Phase 1** — 내부 전사용
  - (A) **입찰 의사결정 지원**: 회차·주차별 최저입찰가/낙찰가 추이 조회
  - (C) **경쟁 브랜드 추적**: 회차별 집행 브랜드 누적
- **Phase 2** — (B) **광고주별 커스텀 리포트**: `/report/[광고주]` 라우트로 분기, 자사 낙찰/경쟁사/놓친 기회/가격 추이 섹션 토글

## 2. 데이터 소스와 수집 방식

### 2.1 NOSP CSV (정형 데이터)

매주 화요일 정기입찰 발표 직후 NOSP에서 4종 CSV가 갱신된다.

| 파일 | 컬럼 |
|------|------|
| `서칭뷰_회차별입찰정보.csv` | 집행회차, 집행기간, 대분류, 소분류, 키워드그룹, 기준조회수, 최저입찰가, 정기입찰기간/발표, 재입찰기간/발표, 입찰가능여부, 현재공실구좌 |
| `서칭뷰_키워드그룹별최근낙찰가.csv` | 대분류, 소분류, 키워드그룹, 최근낙찰가 |
| `신제품_회차별입찰정보.csv` | 동일 |
| `신제품_키워드그룹별최근낙찰가.csv` | 동일 |
| (선택) `회차별키워드셋.csv` | 키워드그룹의 세부 키워드 리스트 — 정원 변동 추적 |

**핵심 제약**

- `최근낙찰가` 는 가장 최근 정기입찰 1건만 노출 → 다음 회차 갱신 시 덮여서 영구 손실
- 재입찰 결과 낙찰가는 별도 공유되지 않음. 단, 재입찰 시작가 = 정기입찰 낙찰가이므로 **정기입찰 낙찰가 1개만 누적해도 정보 손실 없음**
- NOSP 다운로드는 별도 토큰 없이 **로그인 후 다운로드 버튼 클릭** 방식

### 2.2 집행 브랜드 (비정형, 스크래핑)

NOSP에는 낙찰자 정보가 노출되지 않으므로 네이버 검색결과 + 랜딩페이지에서 추출.

**2단계 하이브리드** (광고 클릭은 하지 않음)

1. **DOM scrape**: 네이버 검색결과의 서칭뷰/신제품 광고 영역에서 광고 카드의 `display_name` + `destination URL` 추출
2. **랜딩페이지 직접 방문**: destination URL을 별도 fetch → footer 의 사업자등록상호(`business_name`) 추출 (1단계와 교차 검증)

**규칙**

- 서칭뷰: 키워드그룹당 **1 브랜드** (또는 0 — 집행사 없음)
- 신제품: 키워드그룹당 **최대 2 브랜드** (slot 1/2, 각각 0 가능)
- 수집 빈도: 회차 시작일 +1h 1회
- 신뢰도 < 0.7 항목은 운영 화면의 "검토 큐"로

## 3. 데이터 모델 (Postgres)

```text
products (id, code, name, max_brands_per_group)
  · code: SEARCHING_VIEW | NEW_PRODUCT
  · max_brands_per_group: 1 (서칭뷰) | 2 (신제품)

categories (id, parent_id, name, level)
  · 대분류 ↔ 소분류 self-reference

keyword_groups (id, product_id, category_id, name)
  · 동일 이름이 두 제품에 각각 존재 가능

rounds (id, product_id, round_no, period_start, period_end,
        regular_bid_start, regular_bid_end, regular_announce_date,
        rebid_start, rebid_end, rebid_announce_date)

round_keyword_groups (id, round_id, keyword_group_id,
                      reference_query_volume, min_bid_price,
                      bid_status, empty_slots, keyword_count,
                      regular_winning_bid, captured_at)
  · 회차 × 키워드그룹 unique
  · fact 테이블 (모든 조회의 중심)
  · 재입찰 낙찰가 컬럼 없음 (정보 손실 없음)

round_keywords (id, round_keyword_group_id, keyword)
  · 회차별 세부 키워드 (회차별키워드셋 CSV 출처)

brands (id, business_name, display_name, aliases jsonb)
  · business_name = 사업자등록상호 (정규화 키)
  · display_name = 광고에 보이는 명칭
  · aliases = 동일 광고주의 표기 변형

round_brands (id, round_keyword_group_id, brand_id, slot_no,
              source, confidence, captured_at)
  · slot_no: 신제품 1 or 2, 서칭뷰 항상 1
  · source: dom | landing | manual
  · 0개 케이스는 row 부재 (left join 처리)
  · 수집 실패 sentinel: brand_id=NULL, source='scrape_failed'

clients (id, slug, display_name, brand_ids[], sheet_id, report_config jsonb)
  · Phase 2에서 도입
  · brand_ids = 해당 광고주가 매핑되는 brands.id 다대일

ingest_runs (id, run_type, product_id, file_path, status,
             error_message, run_at, completed_at)
  · run_type: csv_bid_info | csv_winning | brand_scrape | sheet_sync
```

## 4. 적재 파이프라인 (Python 워커, 로컬 PC)

### 4.1 잡 구성

```text
JOB 1: nosp-csv-download        [매주 화 09:30, 12:00]
  - browser-harness 로 NOSP 로그인 세션 복원
  - 다운로드 버튼 클릭 → 4종 CSV (+ 회차별키워드셋) 수집
  - raw/YYYY-MM-DD/ 에 원본 보관 후 JOB 2 트리거

JOB 2: csv-ingest               [JOB 1 완료 시 자동, 또는 --backfill]
  - CSV 파싱 → upsert (rounds, round_keyword_groups, round_keywords)
  - 정기입찰 낙찰가는 발표 타이밍에 맞춰 갱신
  - 멱등성: 같은 회차 재실행 안전
  - ingest_runs 로그 + Slack 요약 알림

JOB 3: brand-scrape             [회차 시작일 +1h, 1회]
  - 활성 회차의 키워드그룹별 대표 키워드 추출
  - 네이버 검색 → 광고 DOM scrape (클릭 없음)
  - destination URL 직접 fetch → footer 사업자명 추출
  - brands 테이블 fuzzy match (rapidfuzz) → 정규화
  - 신제품은 slot 1/2 각각 기록
  - confidence < 0.7 → 검토 큐

JOB 4: sheets-sync              [JOB 2/3 완료 후, 또는 5분 주기]
  - Postgres ↔ Google Sheets 양방향
  - Master Sheet: 전체 fact 테이블 export
  - 시트 수동 보정(브랜드 정정 등) → DB 풀백
  - Phase 2: 광고주별 시트는 master sheet 필터된 view 로 자동 생성
```

### 4.2 폴백 캐스케이드 (B → C → A)

```text
정상 (B 자동):  Tue 09:30 / 12:00 자동 실행
실패 (C 반자동): Slack 알림 → 사용자 "/nosp run" 명령 → 수동 트리거
심각 (A 수동):   inbox/ 폴더에 CSV 드롭 → 폴더 감시 워커가 JOB 2 실행
```

### 4.3 봇 탐지 회피

- 광고 클릭 없음 (DOM href 추출만)
- 요청 간 2~5초 랜덤 딜레이
- 일반 브라우저 UA
- 키워드그룹당 대표 키워드 1~2개로 제한 (총 요청 < 500/회차)
- 실패 임계 도달 시 자동 중단 + Slack 알림

## 5. 대시보드 화면 (Next.js)

좌측 사이드바 + 상단 필터바 공통. 모바일 미고려.

### 5.1 화면 1 — 입찰 의사결정 (홈)

- 키워드그룹 단일 선택 → 회차별 최저/낙찰 라인 차트 + 표
- 표 컬럼: 회차 / 집행기간 / 최저 / 낙찰 / 배수 / 공실 / 집행 브랜드 / 상태
- 신제품은 집행 브랜드 컬럼이 `삼성 / LG` 식 2슬롯 표시
- 인사이트 카드: 평균 배수, 공실 발생률, 추천 입찰가 레인지, **경쟁사 등장 패턴**, **연속 낙찰 시 배수 트렌드**

### 5.2 화면 2 — 회차 현황

- 활성 회차의 전체 키워드그룹 일람
- 필터: 제품 / 카테고리 / 상태 / 브랜드 / 검색
- 집행 브랜드 컬럼 포함 (서칭뷰 1, 신제품 2슬롯)
- 회차 요약: 총 키워드그룹, 입찰가능, 공실 합계, **집행사 0 키워드그룹 수**, 평균 배수

### 5.3 화면 3 — 브랜드 점유

- 카테고리·키워드그룹 단위 회차별 브랜드 히트맵
- 브랜드 상세: 집행 회차 수, 카테고리 분포, 평균 배수, 최근 키워드그룹
- 브랜드 × 회차 × 키워드그룹 표 (소스/신뢰도 표시)

### 5.4 화면 4 — 운영

- `ingest_runs` 최근 20건 (성공/경고/실패)
- 브랜드 검토 큐 (confidence < 0.7) — 후보 brands 목록과 [승인]/[수정] 액션

### 5.5 표시 규칙 (브랜드 컬럼)

| 케이스 | 서칭뷰 | 신제품 |
|--------|--------|--------|
| 1개 집행 | `삼성화재` | `삼성 / -` |
| 2개 집행 | (불가) | `삼성 / LG` |
| 0개 집행 (공실) | `-` | `- / -` |
| 수집 실패 | `?` (검토큐 링크) | `삼성 / ?` |

## 6. Sheets 동기화 (하이브리드 약속)

Master Sheet 1개를 워커가 양방향 동기화한다.

```text
Master Sheet
 ├─ Sheet "round_keyword_groups"  (fact)
 ├─ Sheet "round_brands"          (브랜드 × 회차)
 ├─ Sheet "brands"                (브랜드 마스터)
 └─ Sheet "ingest_runs"           (감사 로그)

DB → Sheet: 5분 주기 또는 적재 직후 push
Sheet → DB: revision API 로 변경 감지 → 브랜드 정정 등 풀백
```

Phase 2 의 광고주 시트는 master sheet 의 필터된 view 로 자동 생성되며 read-only 권한.

## 7. Phase 2 후크

### 7.1 라우트

```text
/                       홈 (의사결정)
/round/[round_no]       회차 현황
/brand                  브랜드 점유
/ops                    운영
/report/[client_slug]   광고주 전용 리포트       ← Phase 2
/report/[client_slug]/sheet  광고주 전용 시트   ← Phase 2
```

### 7.2 광고주 리포트 섹션

`clients.report_config.sections` 으로 토글:

- `own_bids` — 자사 낙찰 현황 (회차·키워드그룹·배수·총 비용)
- `competitors` — 경쟁사 동향 (visible_categories 한정)
- `missed_opportunities` — 입찰 가능했지만 미참여한 회차
- `price_trends` — 자사 표시 강조 라인 차트

### 7.3 접근 제어

- 광고주별 `share_token` URL (Cloudflare Workers 미들웨어 검증)
- 토큰 없으면 404
- 광고주 간 데이터 격리 (`brand_ids` 기준 row-level filter)
- 추후 필요 시 Sign in with Vercel / OAuth 로 확장 가능

## 8. 기술 스택 & 배포

| 레이어 | 선택 |
|--------|------|
| 대시보드 | Next.js 15 (App Router) + TypeScript |
| UI | shadcn/ui + Tailwind |
| 차트 | Recharts |
| ORM | Drizzle ORM |
| DB | **Neon Postgres (Free 0.5GB)** |
| 호스팅 | **Cloudflare Pages** (`@opennextjs/cloudflare`) |
| Cron | **Cloudflare Cron Triggers** (헬스체크) |
| 워커 | Python 3.13 (로컬 Windows PC) |
| 워커 의존 | browser-harness, gspread, psycopg, httpx, beautifulsoup4, rapidfuzz |
| 워커 스케줄 | Windows Task Scheduler |
| 알림 | Slack Incoming Webhook |

### 8.1 디렉토리 구조

```text
SearchingviewNewProduct/
├─ apps/dashboard/                # Next.js
│  ├─ app/
│  │  ├─ page.tsx                 # 화면 1
│  │  ├─ round/[round_no]/
│  │  ├─ brand/
│  │  ├─ ops/
│  │  ├─ report/[slug]/           # Phase 2
│  │  └─ api/{ingest,health}/
│  ├─ components/
│  ├─ lib/db/                     # Drizzle schema
│  └─ wrangler.toml               # Cloudflare 설정
├─ worker/                        # Python 워커
│  ├─ jobs/
│  │  ├─ nosp_download.py         # JOB 1
│  │  ├─ csv_ingest.py            # JOB 2 (--backfill 지원)
│  │  ├─ brand_scrape.py          # JOB 3
│  │  └─ sheets_sync.py           # JOB 4
│  ├─ lib/{nosp,naver_search,landing,slack}.py
│  ├─ run_weekly.py               # 화요일 진입점
│  └─ pyproject.toml
├─ raw/YYYY-MM-DD/                # NOSP CSV 원본 (gitignore)
├─ inbox/                         # 수동 드롭 폴더 (gitignore)
└─ docs/superpowers/specs/        # 이 문서 위치
```

### 8.2 운영 흐름 (한 주)

```text
Tue 09:00  Cloudflare Cron → 헬스체크 → 24h 적재 없으면 Slack 알림
Tue 09:30  로컬 워커 자동 실행 (JOB 1 → 2 → 4) → Slack 요약
Tue 11:00  사용자: 대시보드 → 화면 1 → 이번 주 입찰 결정
Wed-Sat    의사결정 / 브랜드 검토 큐 처리
Mon        회차 시작일 +1h → JOB 3 자동 → Slack 요약
```

### 8.3 비용

| 항목 | 월 비용 |
|------|--------|
| Cloudflare Pages | $0 |
| Cloudflare Cron Triggers | $0 |
| Neon Postgres Free | $0 |
| Google Sheets API | $0 |
| Slack Webhook | $0 |
| **합계** | **$0** |

**확장 시점**: Neon 0.5GB 초과 시(누적 2~3년 후 $19/월), 광고주 트래픽 폭증 시(Workers 100k/일 도달 시 $5/월) — 모두 한참 후 이슈.

### 8.4 보안

- NOSP 로그인 정보: Windows Credential Manager (코드 노출 X)
- 워커 → 대시보드 적재: HMAC 서명 (`INGEST_API_KEY`)
- 광고주 시트: Sheets API viewer 권한
- 브랜드 스크래핑: 광고 클릭 없음, 딜레이, UA, 요청 상한
- 백업: Master Sheet (자연 백업) + Neon 자동 PITR (7일)

## 9. 백필 (이력 데이터)

사용자가 보유한 과거 시트/CSV는 `JOB 2` 의 `--backfill` 모드로 일괄 적재:

```bash
python worker/jobs/csv_ingest.py --backfill --source path/to/legacy_sheet.csv
```

- 회차 번호 기준 멱등 upsert
- 정규화 규칙(브랜드 alias 등)은 inferring 후 사람 확인 큐로

## 10. Phase 1 마일스톤 (5주)

| 주차 | 마일스톤 | 결과물 |
|------|----------|--------|
| W1 | DB 스키마 + JOB 2 (CSV 적재) | inbox/ 드롭 → DB 적재 작동 |
| W2 | 백필 + 화면 1 (입찰 의사결정) | 과거 회차 추이 조회 |
| W3 | JOB 1 (NOSP 자동) + 화면 2 (회차 현황) | 매주 화요일 자동 적재 |
| W4 | JOB 3 (브랜드) + 화면 3 (브랜드 점유) | 경쟁사 추적 |
| W5 | JOB 4 (시트 동기화) + 화면 4 (운영) + Slack | 풀 사이클 + Cloudflare Pages 배포 |

## 11. 검증 필요·열린 항목

- **NOSP 다운로드 자동화 안정성**: 다운로드 버튼 클릭 후 파일명 패턴·다운로드 폴더 권한 확인 필요
- **NOSP 로그인 세션 수명**: 첫 운영에서 확인 후 만료 알림 임계 결정 (기본 2~3개월 가정)
- **광고 destination URL 추출 로직**: 네이버가 트래킹 리다이렉트를 두는 경우 최종 URL 추출 방식 결정
- **footer 사업자명 셀렉터 통일성**: 광고주 사이트마다 다름 → 정규식 패턴 라이브러리 구축 필요
- **Cloudflare Workers Node API 호환성**: 워커 → 대시보드 API의 모든 의존이 Workers 호환인지 빌드 단계에서 확인
- **백필 데이터 포맷**: 사용자가 보유한 과거 시트 컬럼 매핑 — 실제 파일 받는 시점에 매퍼 작성

---

## 부록 A. 화면 1 와이어프레임 (참고)

```text
Filter: [제품: 서칭뷰▾] [대분류: 금융▾] [키워드그룹: 실비보험▾] [기간: 최근 12회차▾]

실비보험 (서칭뷰) — 최근 낙찰가 810k · 공실 1구좌 · 현재 집행: 삼성화재

[라인 차트] 회차별 최저 vs 낙찰 + 브랜드 칩 오버레이

회차   집행기간    최저   낙찰   배수   공실  집행 브랜드   상태
202624 06.08-14   810k   -      -      1구좌  -            가능
202623 06.01-07   810k   810k   1.00x  0     삼성화재     집행중
202622 05.25-31   590k   -      -      -     (집행사 없음) 종료
202621 05.18-24   590k   720k   1.22x  0     메리츠       종료
...

인사이트: 최근 4회차 평균 배수 1.18x · 공실 25% · 추천 850k~950k
경쟁사 패턴: 삼성 5회 / 메리츠 3회 / DB 2회 (12회차)
```

## 부록 B. 화면 2 와이어프레임 (참고)

```text
Round 202624 · 집행 06.08~06.14

키워드그룹   제품    최저    낙찰    배수    공실  집행 브랜드  상태
실비보험     서칭뷰  810k    -       -       1구좌 -           가능
암보험       서칭뷰  540k    700k    1.30x   0    삼성화재    중
쇼파         신제품  1.72M   1.85M   1.08x   0    까사 / 한샘 중
거실테이블   신제품  390k    420k    1.08x   1구좌 까사 / -    가능
...

요약: 총 487 · 입찰가능 23 · 공실 31구좌
     집행사 없음: 서칭뷰 14 · 신제품 8
     평균 배수: 서칭뷰 1.21x · 신제품 1.14x
```
