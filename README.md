# NOSP 입찰 대시보드

네이버 서칭뷰 / 신제품검색 회차·키워드그룹별 입찰가/낙찰가/브랜드 통합 관리.

## Layout

- `apps/dashboard/` — Next.js 15 dashboard (Drizzle + Neon Postgres)
- `worker/` — Python 워커 (CSV 적재, 브랜드 스크래핑, Sheets 동기화)
- `docs/superpowers/` — 설계 문서 & 실행 계획

## Quick start

1. `pnpm install`
2. Copy `.env.example` files to `.env.local` and fill in `DATABASE_URL`
3. `cd apps/dashboard && pnpm drizzle:migrate`
4. `cd worker && uv sync && uv run pytest`

See `docs/superpowers/plans/` for current milestone.

## W1 Dry-run Result (2026-05-20)

End-to-end ingest of 4 NOSP CSVs into Neon Postgres (production DB).

| File | Product | Kind | Rows | Result |
|---|---|---|---|---|
| 서칭뷰_회차별입찰정보 (11).csv | SEARCHING_VIEW | bid_info | 1,114 | inserted |
| 서칭뷰_키워드그룹별최근낙찰가 (11).csv | SEARCHING_VIEW | winning | 371 | updated |
| 신제품_회차별입찰정보 (14).csv | NEW_PRODUCT | bid_info | 6,967 | inserted |
| 신제품_키워드그룹별최근낙찰가 (15).csv | NEW_PRODUCT | winning | 2,320 | updated |

**DB state after ingest:**

| Metric | SEARCHING_VIEW | NEW_PRODUCT |
|---|---|---|
| round_keyword_groups | 1,114 | 6,967 |
| regular_winning_bid filled | 371 | 2,320 |
| keyword_groups | 372 | 2,330 |
| rounds | 3 | 3 |
| categories (total) | 175 | — |

All 4 `ingest_runs` rows in DB with `status = success`.
Archived source files → `raw/2026-05-20/`.

### W2 Screen 1 ready (2026-05-20)

Decision screen live at `pnpm --filter dashboard dev` → http://localhost:3000.
Filters: 제품 / 대분류 / 소분류 / 키워드그룹 / 기간 (회차 단위).

Components:
- Summary card (최근 낙찰가 · 공실 · 현재 집행 — 브랜드는 W4 예정)
- 회차별 라인 차트 (최저입찰가 vs 낙찰가)
- 인사이트 카드 (평균 배수 · 공실률 · 추천 입찰가 레인지)
- 회차 표 (최신순)

Screenshots: `docs/superpowers/screenshots/w2-screen1-{empty,loaded}.png`.
