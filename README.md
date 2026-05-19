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
