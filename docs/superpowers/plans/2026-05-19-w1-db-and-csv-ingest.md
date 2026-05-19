# W1 — Database & CSV Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sign up Neon Postgres, scaffold a Next.js + Python monorepo, define the full DB schema, build a Python CSV ingest job (JOB 2) that consumes the 4 NOSP CSVs and writes to Postgres, and verify end-to-end with the user's real sample files.

**Architecture:** pnpm workspace monorepo holding `apps/dashboard` (Next.js 15 + Drizzle) and `worker/` (Python 3.13 + uv). Drizzle owns schema/migrations; the worker uses raw psycopg + small helper modules. Manual CSV drop to `inbox/` triggers ingest via a watchdog observer.

**Tech Stack:** Next.js 15 App Router, TypeScript, Drizzle ORM, `@neondatabase/serverless`, Neon Postgres (free tier), Python 3.13, uv, psycopg[binary], pydantic, pytest, watchdog, rapidfuzz, structlog.

**Spec reference:** [2026-05-19-nosp-dashboard-design.md](../specs/2026-05-19-nosp-dashboard-design.md) sections 3, 4, 9, 10 (W1).

---

## File Structure

After W1 the repo looks like this. Each file has one clear responsibility.

```
SearchingviewNewProduct/
├─ .gitignore                       # node_modules, .env*, raw/, inbox/, .venv
├─ .editorconfig                    # 2-space indent, LF endings
├─ README.md                        # bootstrap instructions
├─ package.json                     # pnpm workspace root
├─ pnpm-workspace.yaml              # workspaces: ["apps/*"]
├─ apps/
│  └─ dashboard/
│     ├─ package.json
│     ├─ tsconfig.json
│     ├─ next.config.ts
│     ├─ drizzle.config.ts          # Drizzle Kit config
│     ├─ .env.local                 # DATABASE_URL (gitignored)
│     ├─ app/
│     │  └─ page.tsx                # minimal "hello" — W2 fills this in
│     └─ lib/db/
│        ├─ client.ts               # createClient() factory
│        └─ schema/
│           ├─ index.ts             # re-exports all tables
│           ├─ products.ts
│           ├─ categories.ts
│           ├─ keyword_groups.ts
│           ├─ rounds.ts
│           ├─ round_keyword_groups.ts
│           ├─ round_keywords.ts
│           ├─ brands.ts
│           ├─ round_brands.ts
│           ├─ clients.ts           # Phase 2 — empty table now, populated later
│           └─ ingest_runs.ts
├─ apps/dashboard/drizzle/          # generated migration SQL
│  └─ 0000_init.sql                 # produced by drizzle-kit generate
├─ worker/
│  ├─ pyproject.toml
│  ├─ uv.lock                       # generated
│  ├─ .env.local                    # DATABASE_URL (gitignored)
│  ├─ src/worker/
│  │  ├─ __init__.py
│  │  ├─ config.py                  # env loader (pydantic-settings)
│  │  ├─ db.py                      # psycopg connection helper
│  │  ├─ logging.py                 # structlog setup
│  │  ├─ csv_parsers.py             # parsers for the 2 CSV shapes
│  │  ├─ models.py                  # pydantic row models (BidInfoRow, WinningBidRow)
│  │  ├─ upsert.py                  # category/keyword_group/round/round_kg upserts
│  │  ├─ ingest.py                  # orchestrates a single CSV → DB ingest
│  │  ├─ watcher.py                 # inbox/ folder watcher (watchdog)
│  │  └─ jobs/
│  │     ├─ __init__.py
│  │     └─ csv_ingest.py           # JOB 2 entry point (CLI: --file, --backfill, --watch)
│  ├─ tests/
│  │  ├─ conftest.py                # tmp DB fixture (transactional rollback)
│  │  ├─ fixtures/
│  │  │  ├─ sample_bid_info_searching.csv
│  │  │  ├─ sample_bid_info_newproduct.csv
│  │  │  ├─ sample_winning_searching.csv
│  │  │  └─ sample_winning_newproduct.csv
│  │  ├─ test_csv_parsers.py
│  │  ├─ test_upsert.py
│  │  └─ test_ingest_end_to_end.py
│  └─ scripts/
│     └─ seed_products_categories.py  # one-shot seed
├─ raw/                              # gitignored — NOSP CSV originals by date
├─ inbox/                            # gitignored — manual drop folder
└─ docs/superpowers/
   ├─ specs/2026-05-19-nosp-dashboard-design.md
   └─ plans/2026-05-19-w1-db-and-csv-ingest.md   # this file
```

---

## Task 1: Initialize the monorepo

**Files:**
- Create: `.gitignore`, `.editorconfig`, `README.md`, `package.json`, `pnpm-workspace.yaml`

- [ ] **Step 1: Verify prerequisites are installed**

Run:

```powershell
node --version    # expect v20+
pnpm --version    # expect v9+
python --version  # expect 3.13.x
uv --version      # expect any 0.x
git --version
```

Expected: all commands print versions. If any is missing, install before continuing:

- Node 20 LTS: https://nodejs.org/
- pnpm: `npm i -g pnpm`
- Python 3.13: https://www.python.org/downloads/
- uv: `pip install uv` or https://docs.astral.sh/uv/getting-started/installation/

- [ ] **Step 2: Init git repository**

Run:

```powershell
cd C:\Users\MADUP\Documents\SearchingviewNewProduct
git init
git branch -M main
```

Expected: `Initialized empty Git repository in .../SearchingviewNewProduct/.git/`

- [ ] **Step 3: Write `.gitignore`**

Create file `.gitignore`:

```gitignore
# Node
node_modules/
.next/
.turbo/
*.tsbuildinfo
.pnpm-debug.log*

# Env
.env
.env.local
.env.*.local
!.env.example

# Python
__pycache__/
*.py[cod]
.venv/
.uv-cache/
.pytest_cache/
.mypy_cache/

# Worker artifacts
raw/
inbox/

# OS
.DS_Store
Thumbs.db

# IDE
.idea/
.vscode/*
!.vscode/extensions.json
!.vscode/settings.json
```

- [ ] **Step 4: Write `.editorconfig`**

Create file `.editorconfig`:

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
indent_style = space
indent_size = 2
insert_final_newline = true
trim_trailing_whitespace = true

[*.py]
indent_size = 4

[*.md]
trim_trailing_whitespace = false
```

- [ ] **Step 5: Write `README.md`**

Create file `README.md`:

```markdown
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
```

- [ ] **Step 6: Write `pnpm-workspace.yaml`**

Create file `pnpm-workspace.yaml`:

```yaml
packages:
  - "apps/*"
```

- [ ] **Step 7: Write root `package.json`**

Create file `package.json`:

```json
{
  "name": "searchingview-newproduct",
  "private": true,
  "packageManager": "pnpm@9.12.0",
  "scripts": {
    "dashboard:dev": "pnpm --filter dashboard dev",
    "dashboard:build": "pnpm --filter dashboard build",
    "db:generate": "pnpm --filter dashboard drizzle-kit generate",
    "db:migrate": "pnpm --filter dashboard drizzle-kit migrate"
  }
}
```

- [ ] **Step 8: Commit**

```powershell
git add .gitignore .editorconfig README.md package.json pnpm-workspace.yaml
git commit -m "chore: initialize monorepo with pnpm workspace"
```

Expected: commit succeeds.

---

## Task 2: Provision Neon Postgres and capture connection string

**Files:**
- Create: `apps/dashboard/.env.example`, `worker/.env.example`

- [ ] **Step 1: Sign up at Neon**

Open https://console.neon.tech/signup in a browser. Sign up with GitHub or email. Free tier ("Free Plan") is sufficient.

Expected: dashboard view at https://console.neon.tech/app/projects

- [ ] **Step 2: Create a project**

Click "New Project". Settings:

- Project name: `nosp-dashboard`
- Postgres version: 17 (latest default)
- Region: `Asia Pacific (Singapore)` (lowest latency from KR)

Click "Create project". Wait ~10 seconds.

- [ ] **Step 3: Capture the pooled connection string**

On the project dashboard, copy the value under "Connection string" → "Pooled connection" (it starts with `postgresql://` and contains `-pooler.` in the host).

Save it locally. You will paste it into both `.env.local` files in step 4 and 5.

⚠ Do not commit this string. It contains credentials.

- [ ] **Step 4: Write `apps/dashboard/.env.example`**

Create file `apps/dashboard/.env.example`:

```bash
# Copy to .env.local and fill in
DATABASE_URL=postgresql://user:password@host-pooler.region.aws.neon.tech/neondb?sslmode=require
```

- [ ] **Step 5: Write `worker/.env.example`**

Create file `worker/.env.example`:

```bash
# Copy to .env.local and fill in
DATABASE_URL=postgresql://user:password@host-pooler.region.aws.neon.tech/neondb?sslmode=require
```

- [ ] **Step 6: Create gitignored .env.local files**

```powershell
mkdir -Force apps\dashboard
mkdir -Force worker
Copy-Item apps\dashboard\.env.example apps\dashboard\.env.local
Copy-Item worker\.env.example worker\.env.local
```

Then open both `.env.local` files in a text editor and paste the connection string from step 3 as the `DATABASE_URL` value.

- [ ] **Step 7: Verify the connection string works**

Run:

```powershell
$env:DATABASE_URL = (Get-Content apps\dashboard\.env.local | Select-String '^DATABASE_URL=' | ForEach-Object { ($_ -split '=',2)[1] })
psql $env:DATABASE_URL -c "SELECT 1 as ok"
```

Expected: prints a one-row result containing `1`.

If `psql` is not installed, skip this step — Task 4 will catch any connection issue.

- [ ] **Step 8: Commit `.env.example` files only**

```powershell
git add apps/dashboard/.env.example worker/.env.example
git commit -m "chore: add Neon connection string templates"
```

Expected: only the `.env.example` files are committed; `.env.local` files are ignored.

---

## Task 3: Scaffold the Next.js dashboard

**Files:**
- Create: `apps/dashboard/package.json`, `apps/dashboard/tsconfig.json`, `apps/dashboard/next.config.ts`, `apps/dashboard/app/layout.tsx`, `apps/dashboard/app/page.tsx`

- [ ] **Step 1: Create the Next.js app via create-next-app**

Run:

```powershell
cd C:\Users\MADUP\Documents\SearchingviewNewProduct
pnpm create next-app@latest apps/dashboard --typescript --eslint --app --tailwind --src-dir=false --import-alias "@/*" --turbopack --use-pnpm
```

When asked about a `<root>/dashboard` path conflict, answer `N` and let it fill the existing directory. Accept all defaults otherwise.

Expected: `apps/dashboard/` populated with a working Next.js skeleton including `app/page.tsx`.

- [ ] **Step 2: Verify the dev server starts**

Run:

```powershell
pnpm --filter dashboard dev
```

Open http://localhost:3000 in a browser.

Expected: default Next.js welcome page renders.

Press Ctrl+C to stop the dev server.

- [ ] **Step 3: Install Drizzle dependencies**

Run:

```powershell
pnpm --filter dashboard add drizzle-orm @neondatabase/serverless
pnpm --filter dashboard add -D drizzle-kit @types/node tsx dotenv
```

Expected: dependencies added to `apps/dashboard/package.json`.

- [ ] **Step 4: Replace `apps/dashboard/app/page.tsx` with a minimal placeholder**

Overwrite file `apps/dashboard/app/page.tsx`:

```tsx
export default function HomePage() {
  return (
    <main className="min-h-screen flex items-center justify-center">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-semibold">NOSP 입찰 대시보드</h1>
        <p className="text-sm text-gray-500">W2에서 실제 화면 구현 예정.</p>
      </div>
    </main>
  );
}
```

- [ ] **Step 5: Add a db migrate script to `apps/dashboard/package.json`**

Modify `apps/dashboard/package.json` `scripts` section so it contains:

```json
{
  "scripts": {
    "dev": "next dev --turbopack",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "drizzle:generate": "drizzle-kit generate",
    "drizzle:migrate": "drizzle-kit migrate",
    "drizzle:studio": "drizzle-kit studio"
  }
}
```

(Keep the other existing keys like `name`, `version`, `dependencies`, etc. — only the `scripts` object changes.)

- [ ] **Step 6: Commit**

```powershell
git add apps/dashboard package.json pnpm-lock.yaml
git commit -m "feat: scaffold Next.js dashboard with Drizzle deps"
```

---

## Task 4: Wire Drizzle config and DB client

**Files:**
- Create: `apps/dashboard/drizzle.config.ts`, `apps/dashboard/lib/db/client.ts`

- [ ] **Step 1: Write `apps/dashboard/drizzle.config.ts`**

Create file `apps/dashboard/drizzle.config.ts`:

```ts
import { config as loadEnv } from "dotenv";
import { defineConfig } from "drizzle-kit";

loadEnv({ path: ".env.local" });

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL is required for drizzle-kit");
}

export default defineConfig({
  schema: "./lib/db/schema/index.ts",
  out: "./drizzle",
  dialect: "postgresql",
  dbCredentials: {
    url: process.env.DATABASE_URL,
  },
  verbose: true,
  strict: true,
});
```

- [ ] **Step 2: Write `apps/dashboard/lib/db/client.ts`**

Create file `apps/dashboard/lib/db/client.ts`:

```ts
import { neon } from "@neondatabase/serverless";
import { drizzle } from "drizzle-orm/neon-http";
import * as schema from "./schema";

function getUrl(): string {
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new Error("DATABASE_URL is not set");
  }
  return url;
}

export function createDb() {
  const sql = neon(getUrl());
  return drizzle(sql, { schema });
}

export type Db = ReturnType<typeof createDb>;
```

- [ ] **Step 3: Create empty schema index so imports compile**

Create file `apps/dashboard/lib/db/schema/index.ts`:

```ts
// Re-exports all schema tables. Populated by Task 5 onward.
export {};
```

- [ ] **Step 4: Run `drizzle-kit generate` to verify config is valid**

Run:

```powershell
pnpm --filter dashboard drizzle:generate
```

Expected: command succeeds and prints something like "No schema changes detected" (the schema is empty for now).

- [ ] **Step 5: Commit**

```powershell
git add apps/dashboard
git commit -m "feat: wire Drizzle config and Neon client"
```

---

## Task 5: Schema — `products` and `categories`

**Files:**
- Create: `apps/dashboard/lib/db/schema/products.ts`, `apps/dashboard/lib/db/schema/categories.ts`
- Modify: `apps/dashboard/lib/db/schema/index.ts`

- [ ] **Step 1: Write `products.ts`**

Create file `apps/dashboard/lib/db/schema/products.ts`:

```ts
import { pgTable, serial, varchar, smallint, timestamp, uniqueIndex } from "drizzle-orm/pg-core";

export const products = pgTable(
  "products",
  {
    id: serial("id").primaryKey(),
    code: varchar("code", { length: 32 }).notNull(),
    name: varchar("name", { length: 64 }).notNull(),
    maxBrandsPerGroup: smallint("max_brands_per_group").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    codeUq: uniqueIndex("products_code_uq").on(t.code),
  })
);

export type Product = typeof products.$inferSelect;
export type NewProduct = typeof products.$inferInsert;
```

- [ ] **Step 2: Write `categories.ts`**

Create file `apps/dashboard/lib/db/schema/categories.ts`:

```ts
import { pgTable, serial, integer, varchar, smallint, uniqueIndex } from "drizzle-orm/pg-core";

export const categories = pgTable(
  "categories",
  {
    id: serial("id").primaryKey(),
    parentId: integer("parent_id"),
    name: varchar("name", { length: 128 }).notNull(),
    level: smallint("level").notNull(), // 1 = 대분류, 2 = 소분류
  },
  (t) => ({
    nameLevelUq: uniqueIndex("categories_parent_name_uq").on(t.parentId, t.name),
  })
);

export type Category = typeof categories.$inferSelect;
export type NewCategory = typeof categories.$inferInsert;
```

- [ ] **Step 3: Re-export from `index.ts`**

Overwrite file `apps/dashboard/lib/db/schema/index.ts`:

```ts
export * from "./products";
export * from "./categories";
```

- [ ] **Step 4: Generate migration**

Run:

```powershell
pnpm --filter dashboard drizzle:generate
```

Expected: `apps/dashboard/drizzle/0000_<name>.sql` file is created containing CREATE TABLE statements for both tables.

- [ ] **Step 5: Apply migration**

Run:

```powershell
pnpm --filter dashboard drizzle:migrate
```

Expected: success message. Tables now exist in Neon.

- [ ] **Step 6: Verify via Drizzle Studio**

Run:

```powershell
pnpm --filter dashboard drizzle:studio
```

Open the printed URL (https://local.drizzle.studio). Confirm `products` and `categories` tables are visible and empty.

Stop the studio (Ctrl+C).

- [ ] **Step 7: Commit**

```powershell
git add apps/dashboard
git commit -m "feat(db): add products and categories schema"
```

---

## Task 6: Schema — `keyword_groups` and `rounds`

**Files:**
- Create: `apps/dashboard/lib/db/schema/keyword_groups.ts`, `apps/dashboard/lib/db/schema/rounds.ts`
- Modify: `apps/dashboard/lib/db/schema/index.ts`

- [ ] **Step 1: Write `keyword_groups.ts`**

Create file `apps/dashboard/lib/db/schema/keyword_groups.ts`:

```ts
import { pgTable, serial, integer, varchar, uniqueIndex } from "drizzle-orm/pg-core";
import { products } from "./products";
import { categories } from "./categories";

export const keywordGroups = pgTable(
  "keyword_groups",
  {
    id: serial("id").primaryKey(),
    productId: integer("product_id").notNull().references(() => products.id),
    categoryId: integer("category_id").notNull().references(() => categories.id),
    name: varchar("name", { length: 128 }).notNull(),
  },
  (t) => ({
    productNameUq: uniqueIndex("keyword_groups_product_name_uq").on(t.productId, t.name),
  })
);

export type KeywordGroup = typeof keywordGroups.$inferSelect;
export type NewKeywordGroup = typeof keywordGroups.$inferInsert;
```

- [ ] **Step 2: Write `rounds.ts`**

Create file `apps/dashboard/lib/db/schema/rounds.ts`:

```ts
import { pgTable, serial, integer, date, uniqueIndex } from "drizzle-orm/pg-core";
import { products } from "./products";

export const rounds = pgTable(
  "rounds",
  {
    id: serial("id").primaryKey(),
    productId: integer("product_id").notNull().references(() => products.id),
    roundNo: integer("round_no").notNull(), // e.g. 202624
    periodStart: date("period_start").notNull(),
    periodEnd: date("period_end").notNull(),
    regularBidStart: date("regular_bid_start"),
    regularBidEnd: date("regular_bid_end"),
    regularAnnounceDate: date("regular_announce_date"),
    rebidStart: date("rebid_start"),
    rebidEnd: date("rebid_end"),
    rebidAnnounceDate: date("rebid_announce_date"),
  },
  (t) => ({
    productRoundUq: uniqueIndex("rounds_product_round_uq").on(t.productId, t.roundNo),
  })
);

export type Round = typeof rounds.$inferSelect;
export type NewRound = typeof rounds.$inferInsert;
```

- [ ] **Step 3: Update `schema/index.ts`**

Overwrite file `apps/dashboard/lib/db/schema/index.ts`:

```ts
export * from "./products";
export * from "./categories";
export * from "./keyword_groups";
export * from "./rounds";
```

- [ ] **Step 4: Generate and apply migration**

Run:

```powershell
pnpm --filter dashboard drizzle:generate
pnpm --filter dashboard drizzle:migrate
```

Expected: both succeed.

- [ ] **Step 5: Commit**

```powershell
git add apps/dashboard
git commit -m "feat(db): add keyword_groups and rounds schema"
```

---

## Task 7: Schema — `round_keyword_groups` (fact)

**Files:**
- Create: `apps/dashboard/lib/db/schema/round_keyword_groups.ts`
- Modify: `apps/dashboard/lib/db/schema/index.ts`

- [ ] **Step 1: Write `round_keyword_groups.ts`**

Create file `apps/dashboard/lib/db/schema/round_keyword_groups.ts`:

```ts
import {
  pgTable,
  serial,
  integer,
  varchar,
  bigint,
  smallint,
  timestamp,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import { rounds } from "./rounds";
import { keywordGroups } from "./keyword_groups";

export const roundKeywordGroups = pgTable(
  "round_keyword_groups",
  {
    id: serial("id").primaryKey(),
    roundId: integer("round_id").notNull().references(() => rounds.id),
    keywordGroupId: integer("keyword_group_id").notNull().references(() => keywordGroups.id),
    referenceQueryVolume: integer("reference_query_volume"),
    minBidPrice: bigint("min_bid_price", { mode: "number" }),
    bidStatus: varchar("bid_status", { length: 32 }), // 입찰가능 / 입찰기간종료 / 입찰중지
    emptySlots: smallint("empty_slots"),
    keywordCount: smallint("keyword_count"),
    regularWinningBid: bigint("regular_winning_bid", { mode: "number" }),
    capturedAt: timestamp("captured_at", { withTimezone: true }),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    roundKgUq: uniqueIndex("round_keyword_groups_round_kg_uq").on(t.roundId, t.keywordGroupId),
  })
);

export type RoundKeywordGroup = typeof roundKeywordGroups.$inferSelect;
export type NewRoundKeywordGroup = typeof roundKeywordGroups.$inferInsert;
```

- [ ] **Step 2: Update `schema/index.ts`**

Overwrite file `apps/dashboard/lib/db/schema/index.ts`:

```ts
export * from "./products";
export * from "./categories";
export * from "./keyword_groups";
export * from "./rounds";
export * from "./round_keyword_groups";
```

- [ ] **Step 3: Generate and apply migration**

Run:

```powershell
pnpm --filter dashboard drizzle:generate
pnpm --filter dashboard drizzle:migrate
```

Expected: both succeed.

- [ ] **Step 4: Commit**

```powershell
git add apps/dashboard
git commit -m "feat(db): add round_keyword_groups fact table"
```

---

## Task 8: Schema — `round_keywords`, `brands`, `round_brands`

**Files:**
- Create: `apps/dashboard/lib/db/schema/round_keywords.ts`, `brands.ts`, `round_brands.ts`
- Modify: `apps/dashboard/lib/db/schema/index.ts`

- [ ] **Step 1: Write `round_keywords.ts`**

Create file `apps/dashboard/lib/db/schema/round_keywords.ts`:

```ts
import { pgTable, serial, integer, varchar, uniqueIndex } from "drizzle-orm/pg-core";
import { roundKeywordGroups } from "./round_keyword_groups";

export const roundKeywords = pgTable(
  "round_keywords",
  {
    id: serial("id").primaryKey(),
    roundKeywordGroupId: integer("round_keyword_group_id")
      .notNull()
      .references(() => roundKeywordGroups.id, { onDelete: "cascade" }),
    keyword: varchar("keyword", { length: 128 }).notNull(),
  },
  (t) => ({
    rkgKeywordUq: uniqueIndex("round_keywords_rkg_keyword_uq").on(t.roundKeywordGroupId, t.keyword),
  })
);

export type RoundKeyword = typeof roundKeywords.$inferSelect;
export type NewRoundKeyword = typeof roundKeywords.$inferInsert;
```

- [ ] **Step 2: Write `brands.ts`**

Create file `apps/dashboard/lib/db/schema/brands.ts`:

```ts
import { pgTable, serial, varchar, jsonb, timestamp, uniqueIndex } from "drizzle-orm/pg-core";

export const brands = pgTable(
  "brands",
  {
    id: serial("id").primaryKey(),
    businessName: varchar("business_name", { length: 256 }).notNull(), // 사업자등록상호
    displayName: varchar("display_name", { length: 128 }).notNull(),    // 광고 표기
    aliases: jsonb("aliases").$type<string[]>().notNull().default([]),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    businessUq: uniqueIndex("brands_business_uq").on(t.businessName),
  })
);

export type Brand = typeof brands.$inferSelect;
export type NewBrand = typeof brands.$inferInsert;
```

- [ ] **Step 3: Write `round_brands.ts`**

Create file `apps/dashboard/lib/db/schema/round_brands.ts`:

```ts
import {
  pgTable,
  serial,
  integer,
  smallint,
  varchar,
  doublePrecision,
  timestamp,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import { roundKeywordGroups } from "./round_keyword_groups";
import { brands } from "./brands";

export const roundBrands = pgTable(
  "round_brands",
  {
    id: serial("id").primaryKey(),
    roundKeywordGroupId: integer("round_keyword_group_id")
      .notNull()
      .references(() => roundKeywordGroups.id, { onDelete: "cascade" }),
    brandId: integer("brand_id").references(() => brands.id), // nullable for scrape_failed sentinel
    slotNo: smallint("slot_no").notNull(), // 1 or 2 (서칭뷰는 항상 1)
    source: varchar("source", { length: 32 }).notNull(), // dom | landing | manual | scrape_failed
    confidence: doublePrecision("confidence"), // 0~1, NULL for manual
    capturedAt: timestamp("captured_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    rkgSlotUq: uniqueIndex("round_brands_rkg_slot_uq").on(t.roundKeywordGroupId, t.slotNo),
  })
);

export type RoundBrand = typeof roundBrands.$inferSelect;
export type NewRoundBrand = typeof roundBrands.$inferInsert;
```

- [ ] **Step 4: Update `schema/index.ts`**

Overwrite file `apps/dashboard/lib/db/schema/index.ts`:

```ts
export * from "./products";
export * from "./categories";
export * from "./keyword_groups";
export * from "./rounds";
export * from "./round_keyword_groups";
export * from "./round_keywords";
export * from "./brands";
export * from "./round_brands";
```

- [ ] **Step 5: Generate and apply migration**

Run:

```powershell
pnpm --filter dashboard drizzle:generate
pnpm --filter dashboard drizzle:migrate
```

- [ ] **Step 6: Commit**

```powershell
git add apps/dashboard
git commit -m "feat(db): add round_keywords, brands, round_brands schema"
```

---

## Task 9: Schema — `clients` and `ingest_runs`

**Files:**
- Create: `apps/dashboard/lib/db/schema/clients.ts`, `apps/dashboard/lib/db/schema/ingest_runs.ts`
- Modify: `apps/dashboard/lib/db/schema/index.ts`

- [ ] **Step 1: Write `clients.ts`**

Create file `apps/dashboard/lib/db/schema/clients.ts`:

```ts
import { pgTable, serial, varchar, integer, jsonb, timestamp, uniqueIndex } from "drizzle-orm/pg-core";

export const clients = pgTable(
  "clients",
  {
    id: serial("id").primaryKey(),
    slug: varchar("slug", { length: 64 }).notNull(),
    displayName: varchar("display_name", { length: 128 }).notNull(),
    brandIds: jsonb("brand_ids").$type<number[]>().notNull().default([]),
    sheetId: varchar("sheet_id", { length: 128 }),
    reportConfig: jsonb("report_config").$type<Record<string, unknown>>().notNull().default({}),
    createdAt: timestamp("created_at", { withTimezone: true }).defaultNow().notNull(),
  },
  (t) => ({
    slugUq: uniqueIndex("clients_slug_uq").on(t.slug),
  })
);

export type Client = typeof clients.$inferSelect;
export type NewClient = typeof clients.$inferInsert;
```

- [ ] **Step 2: Write `ingest_runs.ts`**

Create file `apps/dashboard/lib/db/schema/ingest_runs.ts`:

```ts
import { pgTable, serial, integer, varchar, text, timestamp } from "drizzle-orm/pg-core";
import { products } from "./products";

export const ingestRuns = pgTable("ingest_runs", {
  id: serial("id").primaryKey(),
  runType: varchar("run_type", { length: 32 }).notNull(), // csv_bid_info | csv_winning | brand_scrape | sheet_sync
  productId: integer("product_id").references(() => products.id),
  filePath: text("file_path"),
  status: varchar("status", { length: 16 }).notNull(), // started | success | error
  errorMessage: text("error_message"),
  rowsTotal: integer("rows_total"),
  rowsInserted: integer("rows_inserted"),
  rowsUpdated: integer("rows_updated"),
  runAt: timestamp("run_at", { withTimezone: true }).defaultNow().notNull(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});

export type IngestRun = typeof ingestRuns.$inferSelect;
export type NewIngestRun = typeof ingestRuns.$inferInsert;
```

- [ ] **Step 3: Update `schema/index.ts`**

Overwrite file `apps/dashboard/lib/db/schema/index.ts`:

```ts
export * from "./products";
export * from "./categories";
export * from "./keyword_groups";
export * from "./rounds";
export * from "./round_keyword_groups";
export * from "./round_keywords";
export * from "./brands";
export * from "./round_brands";
export * from "./clients";
export * from "./ingest_runs";
```

- [ ] **Step 4: Generate and apply migration**

Run:

```powershell
pnpm --filter dashboard drizzle:generate
pnpm --filter dashboard drizzle:migrate
```

Expected: success. All 10 tables now exist in Neon.

- [ ] **Step 5: Commit**

```powershell
git add apps/dashboard
git commit -m "feat(db): add clients and ingest_runs schema"
```

---

## Task 10: Seed `products` rows

**Files:**
- Create: `apps/dashboard/scripts/seed.ts`
- Modify: `apps/dashboard/package.json` (add seed script)

- [ ] **Step 1: Write `apps/dashboard/scripts/seed.ts`**

Create file `apps/dashboard/scripts/seed.ts`:

```ts
import { config as loadEnv } from "dotenv";
loadEnv({ path: ".env.local" });

import { createDb } from "@/lib/db/client";
import { products } from "@/lib/db/schema";

async function main() {
  const db = createDb();

  await db
    .insert(products)
    .values([
      { code: "SEARCHING_VIEW", name: "서칭뷰", maxBrandsPerGroup: 1 },
      { code: "NEW_PRODUCT", name: "신제품검색", maxBrandsPerGroup: 2 },
    ])
    .onConflictDoNothing({ target: products.code });

  const rows = await db.select().from(products);
  console.log(`products in DB (${rows.length}):`);
  for (const r of rows) console.log(`  ${r.code} (max ${r.maxBrandsPerGroup} brands)`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
```

- [ ] **Step 2: Add seed script to `apps/dashboard/package.json`**

In `apps/dashboard/package.json` `scripts`, add:

```json
"db:seed": "tsx scripts/seed.ts"
```

So the full scripts block becomes:

```json
{
  "scripts": {
    "dev": "next dev --turbopack",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "drizzle:generate": "drizzle-kit generate",
    "drizzle:migrate": "drizzle-kit migrate",
    "drizzle:studio": "drizzle-kit studio",
    "db:seed": "tsx scripts/seed.ts"
  }
}
```

- [ ] **Step 3: Run seed**

Run:

```powershell
pnpm --filter dashboard db:seed
```

Expected output:

```
products in DB (2):
  SEARCHING_VIEW (max 1 brands)
  NEW_PRODUCT (max 2 brands)
```

- [ ] **Step 4: Commit**

```powershell
git add apps/dashboard
git commit -m "feat(db): seed products table"
```

---

## Task 11: Initialize Python worker project

**Files:**
- Create: `worker/pyproject.toml`, `worker/src/worker/__init__.py`, `worker/tests/__init__.py`

- [ ] **Step 1: Write `worker/pyproject.toml`**

Create file `worker/pyproject.toml`:

```toml
[project]
name = "worker"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
  "psycopg[binary]>=3.2",
  "pydantic>=2.9",
  "pydantic-settings>=2.6",
  "structlog>=24.4",
  "watchdog>=5.0",
  "python-dotenv>=1.0",
  "rapidfuzz>=3.10",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-cov>=5.0",
  "ruff>=0.7",
]

[tool.uv]
package = true

[tool.hatch.build.targets.wheel]
packages = ["src/worker"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
markers = [
  "db: tests that require a real DATABASE_URL",
]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "RUF"]
```

- [ ] **Step 2: Create source layout files**

Create empty file `worker/src/worker/__init__.py` (no content needed).

Create empty file `worker/tests/__init__.py` (no content needed).

Create empty file `worker/tests/conftest.py` (no content for now — populated in Task 14).

- [ ] **Step 3: Run uv sync to install dependencies and create lockfile**

Run:

```powershell
cd worker
uv sync
cd ..
```

Expected: `worker/.venv/` and `worker/uv.lock` are created. All listed packages install.

- [ ] **Step 4: Smoke test pytest works**

Run:

```powershell
cd worker
uv run pytest -q
cd ..
```

Expected: `no tests ran in 0.XXs` (zero tests is fine — collection succeeded).

- [ ] **Step 5: Commit**

```powershell
git add worker/pyproject.toml worker/uv.lock worker/src worker/tests
git commit -m "feat(worker): initialize Python project with uv"
```

---

## Task 12: Worker config and DB modules

**Files:**
- Create: `worker/src/worker/config.py`, `worker/src/worker/db.py`, `worker/src/worker/logging.py`

- [ ] **Step 1: Write `config.py`**

Create file `worker/src/worker/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 2: Write `logging.py`**

Create file `worker/src/worker/logging.py`:

```python
import logging

import structlog


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
```

- [ ] **Step 3: Write `db.py`**

Create file `worker/src/worker/db.py`:

```python
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection

from worker.config import load_settings


@contextmanager
def connect() -> Iterator[Connection]:
    settings = load_settings()
    with psycopg.connect(settings.database_url, autocommit=False) as conn:
        yield conn
```

- [ ] **Step 4: Add an exploratory smoke test for the connection**

Create file `worker/tests/test_smoke.py`:

```python
import pytest

from worker.db import connect


@pytest.mark.db
def test_connection_returns_one():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
            assert row == (1,)
```

- [ ] **Step 5: Run the smoke test**

Run:

```powershell
cd worker
uv run pytest -m db -v
cd ..
```

Expected: `test_connection_returns_one PASSED`.

If it fails with "DATABASE_URL is not set", confirm `worker/.env.local` has the value from Task 2.

- [ ] **Step 6: Commit**

```powershell
git add worker/src/worker/config.py worker/src/worker/db.py worker/src/worker/logging.py worker/tests/test_smoke.py
git commit -m "feat(worker): add config, db connection, logging modules"
```

---

## Task 13: CSV row models and parsers

**Files:**
- Create: `worker/src/worker/models.py`, `worker/src/worker/csv_parsers.py`
- Create: `worker/tests/fixtures/sample_bid_info_searching.csv`, `worker/tests/fixtures/sample_winning_searching.csv`
- Create: `worker/tests/test_csv_parsers.py`

- [ ] **Step 1: Write `models.py`**

Create file `worker/src/worker/models.py`:

```python
from datetime import date

from pydantic import BaseModel


class BidInfoRow(BaseModel):
    round_no: int
    period_start: date
    period_end: date
    category_lvl1: str
    category_lvl2: str
    keyword_group: str
    reference_query_volume: int
    min_bid_price: int
    regular_bid_start: date
    regular_bid_end: date
    regular_announce_date: date
    rebid_start: date
    rebid_end: date
    rebid_announce_date: date
    bid_status: str
    empty_slots: int


class WinningBidRow(BaseModel):
    category_lvl1: str
    category_lvl2: str
    keyword_group: str
    recent_winning_bid: int
```

- [ ] **Step 2: Create test fixtures with real-looking sample data**

Create file `worker/tests/fixtures/sample_bid_info_searching.csv`:

```csv

서칭뷰 키워드그룹 : 회차별 입찰 정보
조회일자:20260519

! 각 키워드그룹의 집행회차 별 입찰 스케줄 정보입니다.
! 입찰 결과 발표는 발표일 오전 9시이며 일부 지연이 있을 수 있습니다.

집행회차,집행기간,대분류,소분류,키워드그룹,기준조회수,최저입찰가,정기입찰기간,정기입찰발표,재입찰기간,재입찰발표,입찰가능여부,현재공실구좌
202622,20260525~20260531,금융,금융상품,실비보험,15000,590000,20260428~20260511,20260512,20260513~20260518,20260519,입찰기간종료,0
202623,20260601~20260607,금융,금융상품,실비보험,15500,810000,20260512~20260518,20260519,20260520~20260525,20260526,입찰중지,0
202624,20260608~20260614,금융,금융상품,실비보험,15700,810000,20260519~20260525,20260526,20260527~20260601,20260602,입찰가능(1구좌),1
```

Create file `worker/tests/fixtures/sample_winning_searching.csv`:

```csv

서칭뷰 키워드그룹 : 최근낙찰가
조회일자:20260519

! 각 키워드 그룹의 조회 시점 기준으로 가장 최근에 결과가 발표된 정기입찰 건의 낙찰가 입니다.

대분류,소분류,키워드그룹,최근낙찰가
금융,금융상품,실비보험,810000
```

- [ ] **Step 3: Write failing parser tests**

Create file `worker/tests/test_csv_parsers.py`:

```python
from datetime import date
from pathlib import Path

import pytest

from worker.csv_parsers import parse_bid_info_csv, parse_winning_bid_csv

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_bid_info_csv_skips_preamble():
    rows = list(parse_bid_info_csv(FIXTURES / "sample_bid_info_searching.csv"))
    assert len(rows) == 3


def test_parse_bid_info_csv_parses_round_202624():
    rows = list(parse_bid_info_csv(FIXTURES / "sample_bid_info_searching.csv"))
    r = next(row for row in rows if row.round_no == 202624)
    assert r.period_start == date(2026, 6, 8)
    assert r.period_end == date(2026, 6, 14)
    assert r.category_lvl1 == "금융"
    assert r.category_lvl2 == "금융상품"
    assert r.keyword_group == "실비보험"
    assert r.min_bid_price == 810_000
    assert r.regular_announce_date == date(2026, 5, 26)
    assert r.rebid_announce_date == date(2026, 6, 2)
    assert r.bid_status == "입찰가능(1구좌)"
    assert r.empty_slots == 1


def test_parse_bid_info_csv_handles_zero_empty_slots():
    rows = list(parse_bid_info_csv(FIXTURES / "sample_bid_info_searching.csv"))
    r = next(row for row in rows if row.round_no == 202622)
    assert r.empty_slots == 0


def test_parse_winning_bid_csv_returns_rows():
    rows = list(parse_winning_bid_csv(FIXTURES / "sample_winning_searching.csv"))
    assert len(rows) == 1
    assert rows[0].keyword_group == "실비보험"
    assert rows[0].recent_winning_bid == 810_000
```

- [ ] **Step 4: Run tests to verify they fail**

Run:

```powershell
cd worker
uv run pytest tests/test_csv_parsers.py -v
cd ..
```

Expected: ImportError because `csv_parsers` does not exist yet.

- [ ] **Step 5: Implement `csv_parsers.py`**

Create file `worker/src/worker/csv_parsers.py`:

```python
import csv
from collections.abc import Iterator
from datetime import date
from pathlib import Path
import re

from worker.models import BidInfoRow, WinningBidRow

BID_INFO_HEADER = "집행회차"
WINNING_HEADER = "대분류"

_DATE = re.compile(r"^\d{8}$")


def _parse_date(s: str) -> date:
    s = s.strip()
    if not _DATE.match(s):
        raise ValueError(f"unexpected date format: {s!r}")
    return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))


def _parse_date_range(s: str) -> tuple[date, date]:
    a, b = s.split("~")
    return _parse_date(a), _parse_date(b)


def _iter_data_rows(path: Path, header_first_col: str) -> Iterator[list[str]]:
    """Yield csv rows starting after the header line whose first column matches."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        in_data = False
        headers: list[str] = []
        for row in reader:
            if not row:
                continue
            if not in_data:
                if row[0].strip() == header_first_col:
                    in_data = True
                    headers = [c.strip() for c in row]
                continue
            if len(row) < len(headers):
                continue
            yield row


def parse_bid_info_csv(path: Path) -> Iterator[BidInfoRow]:
    for row in _iter_data_rows(path, BID_INFO_HEADER):
        period_start, period_end = _parse_date_range(row[1])
        reg_start, reg_end = _parse_date_range(row[7])
        rebid_start, rebid_end = _parse_date_range(row[9])
        empty_str = row[13].strip()
        empty_slots = int(empty_str) if empty_str.isdigit() else 0
        yield BidInfoRow(
            round_no=int(row[0]),
            period_start=period_start,
            period_end=period_end,
            category_lvl1=row[2].strip(),
            category_lvl2=row[3].strip(),
            keyword_group=row[4].strip(),
            reference_query_volume=int(row[5]),
            min_bid_price=int(row[6]),
            regular_bid_start=reg_start,
            regular_bid_end=reg_end,
            regular_announce_date=_parse_date(row[8]),
            rebid_start=rebid_start,
            rebid_end=rebid_end,
            rebid_announce_date=_parse_date(row[10]),
            bid_status=row[11].strip(),
            empty_slots=empty_slots,
        )


def parse_winning_bid_csv(path: Path) -> Iterator[WinningBidRow]:
    for row in _iter_data_rows(path, WINNING_HEADER):
        yield WinningBidRow(
            category_lvl1=row[0].strip(),
            category_lvl2=row[1].strip(),
            keyword_group=row[2].strip(),
            recent_winning_bid=int(row[3]),
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```powershell
cd worker
uv run pytest tests/test_csv_parsers.py -v
cd ..
```

Expected: 4 tests pass.

- [ ] **Step 7: Commit**

```powershell
git add worker/src/worker/models.py worker/src/worker/csv_parsers.py worker/tests/fixtures worker/tests/test_csv_parsers.py
git commit -m "feat(worker): add CSV parsers for bid info and winning bid"
```

---

## Task 14: Test fixtures and DB-isolation conftest

**Files:**
- Modify: `worker/tests/conftest.py`

- [ ] **Step 1: Write `conftest.py` with a transactional DB fixture**

Overwrite file `worker/tests/conftest.py`:

```python
"""Shared fixtures.

`db_conn` opens a real Neon connection wrapped in a SAVEPOINT that is rolled
back after each test, so production data is never mutated.
"""

from collections.abc import Iterator

import psycopg
import pytest

from worker.config import load_settings


@pytest.fixture
def db_conn() -> Iterator[psycopg.Connection]:
    settings = load_settings()
    conn = psycopg.connect(settings.database_url, autocommit=False)
    try:
        with conn.transaction():  # outer tx — rolled back at fixture teardown
            yield conn
            raise _Rollback
    except _Rollback:
        pass
    finally:
        conn.close()


class _Rollback(Exception):
    pass
```

- [ ] **Step 2: Verify smoke test still passes (it uses `connect()`, not the fixture)**

Run:

```powershell
cd worker
uv run pytest tests/test_smoke.py -v
cd ..
```

Expected: PASS.

- [ ] **Step 3: Commit**

```powershell
git add worker/tests/conftest.py
git commit -m "test(worker): add transactional db_conn fixture"
```

---

## Task 15: Upsert helpers — categories and keyword groups

**Files:**
- Create: `worker/src/worker/upsert.py`
- Create: `worker/tests/test_upsert.py`

- [ ] **Step 1: Write failing tests for category upserts**

Create file `worker/tests/test_upsert.py`:

```python
import pytest

from worker.upsert import (
    upsert_category_pair,
    upsert_keyword_group,
)

pytestmark = pytest.mark.db


def test_upsert_category_pair_creates_both_levels(db_conn):
    lvl1_id, lvl2_id = upsert_category_pair(db_conn, "금융", "금융상품")
    assert lvl1_id and lvl2_id and lvl1_id != lvl2_id

    # idempotent
    lvl1_id2, lvl2_id2 = upsert_category_pair(db_conn, "금융", "금융상품")
    assert lvl1_id == lvl1_id2
    assert lvl2_id == lvl2_id2


def test_upsert_keyword_group_is_unique_per_product(db_conn):
    _, lvl2 = upsert_category_pair(db_conn, "금융", "금융상품")

    # product 1 (서칭뷰) and product 2 (신제품) come from the seed
    cur = db_conn.cursor()
    cur.execute("SELECT id FROM products WHERE code = 'SEARCHING_VIEW'")
    sv_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM products WHERE code = 'NEW_PRODUCT'")
    np_id = cur.fetchone()[0]

    sv_kg = upsert_keyword_group(db_conn, sv_id, lvl2, "실비보험")
    np_kg = upsert_keyword_group(db_conn, np_id, lvl2, "실비보험")
    assert sv_kg != np_kg

    again = upsert_keyword_group(db_conn, sv_id, lvl2, "실비보험")
    assert again == sv_kg
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
cd worker
uv run pytest tests/test_upsert.py -v
cd ..
```

Expected: ImportError — `worker.upsert` does not exist yet.

- [ ] **Step 3: Implement `upsert.py`**

Create file `worker/src/worker/upsert.py`:

```python
from psycopg import Connection


def upsert_category_pair(conn: Connection, lvl1: str, lvl2: str) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO categories (parent_id, name, level)
            VALUES (NULL, %s, 1)
            ON CONFLICT (parent_id, name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (lvl1,),
        )
        lvl1_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO categories (parent_id, name, level)
            VALUES (%s, %s, 2)
            ON CONFLICT (parent_id, name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            (lvl1_id, lvl2),
        )
        lvl2_id = cur.fetchone()[0]
    return lvl1_id, lvl2_id


def upsert_keyword_group(conn: Connection, product_id: int, category_id: int, name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO keyword_groups (product_id, category_id, name)
            VALUES (%s, %s, %s)
            ON CONFLICT (product_id, name) DO UPDATE SET category_id = EXCLUDED.category_id
            RETURNING id
            """,
            (product_id, category_id, name),
        )
        return cur.fetchone()[0]
```

- [ ] **Step 4: Note about unique constraints**

The `ON CONFLICT (parent_id, name)` in categories matches the `categories_parent_name_uq` index from Task 5. Postgres treats `NULL` as distinct in unique indexes by default — but we need `(NULL, '금융')` to match itself. Drizzle's `uniqueIndex` does **not** by default include `NULLS NOT DISTINCT`, so we need to alter the index.

Create migration manually. Run:

```powershell
cd apps\dashboard
pnpm exec drizzle-kit generate --custom
```

When prompted for a name, type: `categories_nulls_not_distinct`. A new empty migration file appears under `apps/dashboard/drizzle/`.

Open the newly created `.sql` file and replace its contents with:

```sql
DROP INDEX IF EXISTS "categories_parent_name_uq";
CREATE UNIQUE INDEX "categories_parent_name_uq" ON "categories" ("parent_id", "name") NULLS NOT DISTINCT;
```

Then apply it:

```powershell
pnpm drizzle:migrate
cd ..\..
```

Expected: migration succeeds.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```powershell
cd worker
uv run pytest tests/test_upsert.py -v -m db
cd ..
```

Expected: 2 tests pass.

- [ ] **Step 6: Commit**

```powershell
git add apps/dashboard/drizzle worker/src/worker/upsert.py worker/tests/test_upsert.py
git commit -m "feat(worker): upsert helpers for categories and keyword groups"
```

---

## Task 16: Upsert helpers — rounds and round_keyword_groups

**Files:**
- Modify: `worker/src/worker/upsert.py`
- Modify: `worker/tests/test_upsert.py`

- [ ] **Step 1: Add failing tests for round + round_keyword_group upserts**

Append to `worker/tests/test_upsert.py`:

```python
from datetime import date

from worker.upsert import upsert_round, upsert_round_keyword_group


def test_upsert_round_is_idempotent(db_conn):
    cur = db_conn.cursor()
    cur.execute("SELECT id FROM products WHERE code = 'SEARCHING_VIEW'")
    sv_id = cur.fetchone()[0]

    r1 = upsert_round(
        db_conn,
        product_id=sv_id,
        round_no=202624,
        period_start=date(2026, 6, 8),
        period_end=date(2026, 6, 14),
        regular_bid_start=date(2026, 5, 19),
        regular_bid_end=date(2026, 5, 25),
        regular_announce_date=date(2026, 5, 26),
        rebid_start=date(2026, 5, 27),
        rebid_end=date(2026, 6, 1),
        rebid_announce_date=date(2026, 6, 2),
    )
    r2 = upsert_round(
        db_conn,
        product_id=sv_id,
        round_no=202624,
        period_start=date(2026, 6, 8),
        period_end=date(2026, 6, 14),
        regular_bid_start=date(2026, 5, 19),
        regular_bid_end=date(2026, 5, 25),
        regular_announce_date=date(2026, 5, 26),
        rebid_start=date(2026, 5, 27),
        rebid_end=date(2026, 6, 1),
        rebid_announce_date=date(2026, 6, 2),
    )
    assert r1 == r2


def test_upsert_round_keyword_group_updates_status(db_conn):
    cur = db_conn.cursor()
    cur.execute("SELECT id FROM products WHERE code = 'SEARCHING_VIEW'")
    sv_id = cur.fetchone()[0]

    _, lvl2 = upsert_category_pair(db_conn, "금융", "금융상품")
    kg_id = upsert_keyword_group(db_conn, sv_id, lvl2, "실비보험")
    round_id = upsert_round(
        db_conn,
        product_id=sv_id,
        round_no=202624,
        period_start=date(2026, 6, 8),
        period_end=date(2026, 6, 14),
    )

    rkg1 = upsert_round_keyword_group(
        db_conn,
        round_id=round_id,
        keyword_group_id=kg_id,
        reference_query_volume=15700,
        min_bid_price=810_000,
        bid_status="입찰가능",
        empty_slots=1,
    )
    rkg2 = upsert_round_keyword_group(
        db_conn,
        round_id=round_id,
        keyword_group_id=kg_id,
        reference_query_volume=15700,
        min_bid_price=810_000,
        bid_status="입찰기간종료",
        empty_slots=0,
    )
    assert rkg1 == rkg2

    cur.execute("SELECT bid_status, empty_slots FROM round_keyword_groups WHERE id = %s", (rkg1,))
    status, slots = cur.fetchone()
    assert status == "입찰기간종료"
    assert slots == 0
```

- [ ] **Step 2: Verify the new tests fail**

Run:

```powershell
cd worker
uv run pytest tests/test_upsert.py -v -m db
cd ..
```

Expected: ImportError for `upsert_round` and `upsert_round_keyword_group`.

- [ ] **Step 3: Extend `worker/src/worker/upsert.py`**

Append to file `worker/src/worker/upsert.py`:

```python
from datetime import date


def upsert_round(
    conn: Connection,
    *,
    product_id: int,
    round_no: int,
    period_start: date,
    period_end: date,
    regular_bid_start: date | None = None,
    regular_bid_end: date | None = None,
    regular_announce_date: date | None = None,
    rebid_start: date | None = None,
    rebid_end: date | None = None,
    rebid_announce_date: date | None = None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO rounds (
                product_id, round_no, period_start, period_end,
                regular_bid_start, regular_bid_end, regular_announce_date,
                rebid_start, rebid_end, rebid_announce_date
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (product_id, round_no) DO UPDATE SET
                period_start = EXCLUDED.period_start,
                period_end = EXCLUDED.period_end,
                regular_bid_start = EXCLUDED.regular_bid_start,
                regular_bid_end = EXCLUDED.regular_bid_end,
                regular_announce_date = EXCLUDED.regular_announce_date,
                rebid_start = EXCLUDED.rebid_start,
                rebid_end = EXCLUDED.rebid_end,
                rebid_announce_date = EXCLUDED.rebid_announce_date
            RETURNING id
            """,
            (
                product_id,
                round_no,
                period_start,
                period_end,
                regular_bid_start,
                regular_bid_end,
                regular_announce_date,
                rebid_start,
                rebid_end,
                rebid_announce_date,
            ),
        )
        return cur.fetchone()[0]


def upsert_round_keyword_group(
    conn: Connection,
    *,
    round_id: int,
    keyword_group_id: int,
    reference_query_volume: int | None = None,
    min_bid_price: int | None = None,
    bid_status: str | None = None,
    empty_slots: int | None = None,
    keyword_count: int | None = None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO round_keyword_groups (
                round_id, keyword_group_id,
                reference_query_volume, min_bid_price, bid_status, empty_slots, keyword_count,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (round_id, keyword_group_id) DO UPDATE SET
                reference_query_volume = EXCLUDED.reference_query_volume,
                min_bid_price = EXCLUDED.min_bid_price,
                bid_status = EXCLUDED.bid_status,
                empty_slots = EXCLUDED.empty_slots,
                keyword_count = COALESCE(EXCLUDED.keyword_count, round_keyword_groups.keyword_count),
                updated_at = now()
            RETURNING id
            """,
            (
                round_id,
                keyword_group_id,
                reference_query_volume,
                min_bid_price,
                bid_status,
                empty_slots,
                keyword_count,
            ),
        )
        return cur.fetchone()[0]


def update_winning_bid(
    conn: Connection,
    *,
    round_keyword_group_id: int,
    winning_bid: int,
) -> None:
    """Set regular_winning_bid + captured_at for a round_keyword_group."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE round_keyword_groups
            SET regular_winning_bid = %s, captured_at = now(), updated_at = now()
            WHERE id = %s
            """,
            (winning_bid, round_keyword_group_id),
        )
```

- [ ] **Step 4: Run all upsert tests**

Run:

```powershell
cd worker
uv run pytest tests/test_upsert.py -v -m db
cd ..
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```powershell
git add worker/src/worker/upsert.py worker/tests/test_upsert.py
git commit -m "feat(worker): upsert helpers for rounds and round_keyword_groups"
```

---

## Task 17: `ingest_runs` lifecycle helper

**Files:**
- Modify: `worker/src/worker/upsert.py`
- Create: `worker/tests/test_ingest_runs.py`

- [ ] **Step 1: Write failing test**

Create file `worker/tests/test_ingest_runs.py`:

```python
import pytest

from worker.upsert import complete_ingest_run, fail_ingest_run, start_ingest_run

pytestmark = pytest.mark.db


def test_start_then_complete_ingest_run(db_conn):
    run_id = start_ingest_run(db_conn, run_type="csv_bid_info", file_path="raw/foo.csv")
    assert isinstance(run_id, int)

    complete_ingest_run(
        db_conn, run_id=run_id, rows_total=100, rows_inserted=80, rows_updated=20
    )

    cur = db_conn.cursor()
    cur.execute(
        "SELECT status, rows_inserted, rows_updated FROM ingest_runs WHERE id = %s",
        (run_id,),
    )
    status, ins, upd = cur.fetchone()
    assert status == "success"
    assert ins == 80
    assert upd == 20


def test_start_then_fail_ingest_run(db_conn):
    run_id = start_ingest_run(db_conn, run_type="csv_winning", file_path="raw/bar.csv")
    fail_ingest_run(db_conn, run_id=run_id, error_message="boom")

    cur = db_conn.cursor()
    cur.execute("SELECT status, error_message FROM ingest_runs WHERE id = %s", (run_id,))
    status, err = cur.fetchone()
    assert status == "error"
    assert err == "boom"
```

- [ ] **Step 2: Verify it fails**

Run:

```powershell
cd worker
uv run pytest tests/test_ingest_runs.py -v -m db
cd ..
```

Expected: ImportError.

- [ ] **Step 3: Implement the helpers**

Append to file `worker/src/worker/upsert.py`:

```python
def start_ingest_run(
    conn: Connection,
    *,
    run_type: str,
    file_path: str | None = None,
    product_id: int | None = None,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingest_runs (run_type, product_id, file_path, status)
            VALUES (%s, %s, %s, 'started')
            RETURNING id
            """,
            (run_type, product_id, file_path),
        )
        return cur.fetchone()[0]


def complete_ingest_run(
    conn: Connection,
    *,
    run_id: int,
    rows_total: int | None = None,
    rows_inserted: int | None = None,
    rows_updated: int | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_runs
            SET status = 'success',
                rows_total = %s,
                rows_inserted = %s,
                rows_updated = %s,
                completed_at = now()
            WHERE id = %s
            """,
            (rows_total, rows_inserted, rows_updated, run_id),
        )


def fail_ingest_run(conn: Connection, *, run_id: int, error_message: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ingest_runs
            SET status = 'error', error_message = %s, completed_at = now()
            WHERE id = %s
            """,
            (error_message, run_id),
        )
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
cd worker
uv run pytest tests/test_ingest_runs.py -v -m db
cd ..
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```powershell
git add worker/src/worker/upsert.py worker/tests/test_ingest_runs.py
git commit -m "feat(worker): ingest_runs lifecycle helpers"
```

---

## Task 18: End-to-end ingest orchestrator

**Files:**
- Create: `worker/src/worker/ingest.py`
- Create: `worker/tests/test_ingest_end_to_end.py`

- [ ] **Step 1: Write failing end-to-end test**

Create file `worker/tests/test_ingest_end_to_end.py`:

```python
from pathlib import Path

import pytest

from worker.ingest import ingest_csv

FIXTURES = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.db


def test_ingest_bid_info_creates_rounds_and_rkg(db_conn):
    result = ingest_csv(
        db_conn,
        path=FIXTURES / "sample_bid_info_searching.csv",
        product_code="SEARCHING_VIEW",
        kind="bid_info",
    )
    assert result.rows_total == 3
    assert result.rows_inserted == 3
    assert result.rows_updated == 0

    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT r.round_no, rkg.min_bid_price, rkg.bid_status, rkg.empty_slots
        FROM round_keyword_groups rkg
        JOIN rounds r ON r.id = rkg.round_id
        JOIN products p ON p.id = r.product_id
        WHERE p.code = 'SEARCHING_VIEW'
        ORDER BY r.round_no
        """
    )
    rows = cur.fetchall()
    assert rows == [
        (202622, 590_000, "입찰기간종료", 0),
        (202623, 810_000, "입찰중지", 0),
        (202624, 810_000, "입찰가능(1구좌)", 1),
    ]


def test_ingest_winning_then_bid_info_preserves_winning(db_conn):
    # Bid info first
    ingest_csv(
        db_conn,
        path=FIXTURES / "sample_bid_info_searching.csv",
        product_code="SEARCHING_VIEW",
        kind="bid_info",
    )
    # Then winning
    result = ingest_csv(
        db_conn,
        path=FIXTURES / "sample_winning_searching.csv",
        product_code="SEARCHING_VIEW",
        kind="winning",
    )
    assert result.rows_total == 1
    assert result.rows_updated == 1

    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT r.round_no, rkg.regular_winning_bid
        FROM round_keyword_groups rkg
        JOIN rounds r ON r.id = rkg.round_id
        ORDER BY r.round_no DESC
        LIMIT 1
        """
    )
    round_no, winning = cur.fetchone()
    # 최근낙찰가 attaches to the latest announced 정기입찰. For our fixture,
    # the latest 정기입찰발표 in the bid_info file is 20260526 (round 202623).
    # See Task 18 step 2 design notes for why we pick that row.
    assert round_no == 202623
    assert winning == 810_000


def test_ingest_is_idempotent(db_conn):
    r1 = ingest_csv(
        db_conn,
        path=FIXTURES / "sample_bid_info_searching.csv",
        product_code="SEARCHING_VIEW",
        kind="bid_info",
    )
    r2 = ingest_csv(
        db_conn,
        path=FIXTURES / "sample_bid_info_searching.csv",
        product_code="SEARCHING_VIEW",
        kind="bid_info",
    )
    assert r1.rows_inserted == 3
    assert r2.rows_inserted == 0
    assert r2.rows_updated == 3
```

- [ ] **Step 2: Design note — which round gets the winning bid**

The 최근낙찰가 CSV doesn't say which round the winning bid belongs to. By the NOSP semantic: "가장 최근에 결과가 발표된 정기입찰 건의 낙찰가". So we attach it to the round whose `regular_announce_date` is the **latest** that is **≤ the CSV's 조회일자**.

For the W1 sample fixtures the 조회일자 is 20260519. The 정기입찰발표 dates in the bid_info fixture are 20260512, 20260519, 20260526. The latest ≤ 20260519 is 20260519 → round 202623.

This rule is encoded in `ingest.py` Step 3.

- [ ] **Step 3: Implement `ingest.py`**

Create file `worker/src/worker/ingest.py`:

```python
"""High-level CSV → DB orchestrator (JOB 2)."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re

from psycopg import Connection

from worker.csv_parsers import parse_bid_info_csv, parse_winning_bid_csv
from worker.logging import get_logger
from worker.models import BidInfoRow, WinningBidRow
from worker.upsert import (
    complete_ingest_run,
    fail_ingest_run,
    start_ingest_run,
    update_winning_bid,
    upsert_category_pair,
    upsert_keyword_group,
    upsert_round,
    upsert_round_keyword_group,
)

log = get_logger(__name__)

_QUERY_DATE = re.compile(r"조회일자\s*[:：]\s*(\d{8})")


@dataclass
class IngestResult:
    rows_total: int
    rows_inserted: int
    rows_updated: int
    run_id: int


def _read_query_date(path: Path) -> date:
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            m = _QUERY_DATE.search(line)
            if m:
                s = m.group(1)
                return date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    raise ValueError(f"조회일자 not found in {path}")


def _product_id(conn: Connection, code: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM products WHERE code = %s", (code,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"product not found: {code}")
        return row[0]


def ingest_csv(
    conn: Connection,
    *,
    path: Path,
    product_code: str,
    kind: str,  # "bid_info" | "winning"
) -> IngestResult:
    run_type = "csv_bid_info" if kind == "bid_info" else "csv_winning"
    product_id = _product_id(conn, product_code)
    run_id = start_ingest_run(
        conn, run_type=run_type, file_path=str(path), product_id=product_id
    )

    try:
        if kind == "bid_info":
            result = _ingest_bid_info(conn, path, product_id, run_id)
        elif kind == "winning":
            result = _ingest_winning(conn, path, product_id, run_id)
        else:
            raise ValueError(f"unknown kind: {kind}")
        complete_ingest_run(
            conn,
            run_id=run_id,
            rows_total=result.rows_total,
            rows_inserted=result.rows_inserted,
            rows_updated=result.rows_updated,
        )
        return result
    except Exception as exc:
        fail_ingest_run(conn, run_id=run_id, error_message=str(exc))
        raise


def _ingest_bid_info(
    conn: Connection, path: Path, product_id: int, run_id: int
) -> IngestResult:
    total = inserted = updated = 0
    for row in parse_bid_info_csv(path):
        before = _row_exists_for(conn, product_id, row)
        _, lvl2 = upsert_category_pair(conn, row.category_lvl1, row.category_lvl2)
        kg_id = upsert_keyword_group(conn, product_id, lvl2, row.keyword_group)
        round_id = upsert_round(
            conn,
            product_id=product_id,
            round_no=row.round_no,
            period_start=row.period_start,
            period_end=row.period_end,
            regular_bid_start=row.regular_bid_start,
            regular_bid_end=row.regular_bid_end,
            regular_announce_date=row.regular_announce_date,
            rebid_start=row.rebid_start,
            rebid_end=row.rebid_end,
            rebid_announce_date=row.rebid_announce_date,
        )
        upsert_round_keyword_group(
            conn,
            round_id=round_id,
            keyword_group_id=kg_id,
            reference_query_volume=row.reference_query_volume,
            min_bid_price=row.min_bid_price,
            bid_status=row.bid_status,
            empty_slots=row.empty_slots,
        )
        total += 1
        if before:
            updated += 1
        else:
            inserted += 1
    log.info("bid_info ingested", total=total, inserted=inserted, updated=updated)
    return IngestResult(total, inserted, updated, run_id)


def _row_exists_for(conn: Connection, product_id: int, row: BidInfoRow) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM round_keyword_groups rkg
            JOIN rounds r  ON r.id  = rkg.round_id  AND r.product_id  = %s AND r.round_no = %s
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id AND kg.product_id = %s AND kg.name = %s
            LIMIT 1
            """,
            (product_id, row.round_no, product_id, row.keyword_group),
        )
        return cur.fetchone() is not None


def _ingest_winning(
    conn: Connection, path: Path, product_id: int, run_id: int
) -> IngestResult:
    query_date = _read_query_date(path)
    total = updated = 0
    for row in parse_winning_bid_csv(path):
        rkg_id = _latest_announced_rkg(conn, product_id, row, query_date)
        if rkg_id is None:
            log.warning(
                "no round to attach winning bid",
                product_id=product_id,
                keyword_group=row.keyword_group,
            )
            continue
        update_winning_bid(conn, round_keyword_group_id=rkg_id, winning_bid=row.recent_winning_bid)
        total += 1
        updated += 1
    return IngestResult(total, 0, updated, run_id)


def _latest_announced_rkg(
    conn: Connection, product_id: int, row: WinningBidRow, query_date: date
) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rkg.id
            FROM round_keyword_groups rkg
            JOIN rounds r  ON r.id  = rkg.round_id  AND r.product_id  = %s
            JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id AND kg.product_id = %s AND kg.name = %s
            WHERE r.regular_announce_date IS NOT NULL
              AND r.regular_announce_date <= %s
            ORDER BY r.regular_announce_date DESC
            LIMIT 1
            """,
            (product_id, product_id, row.keyword_group, query_date),
        )
        row = cur.fetchone()
        return row[0] if row else None
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
cd worker
uv run pytest tests/test_ingest_end_to_end.py -v -m db
cd ..
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```powershell
git add worker/src/worker/ingest.py worker/tests/test_ingest_end_to_end.py
git commit -m "feat(worker): end-to-end CSV ingest orchestrator"
```

---

## Task 19: `csv_ingest` CLI entry point with file mode

**Files:**
- Create: `worker/src/worker/jobs/__init__.py`, `worker/src/worker/jobs/csv_ingest.py`

- [ ] **Step 1: Create empty `worker/src/worker/jobs/__init__.py`** (empty file)

- [ ] **Step 2: Write `csv_ingest.py` CLI**

Create file `worker/src/worker/jobs/csv_ingest.py`:

```python
"""JOB 2: CSV ingest.

Usage:
    uv run python -m worker.jobs.csv_ingest --file path/to/file.csv --product SEARCHING_VIEW --kind bid_info
    uv run python -m worker.jobs.csv_ingest --watch          # watches inbox/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from worker.db import connect
from worker.ingest import ingest_csv
from worker.logging import configure_logging, get_logger

log = get_logger(__name__)


def _detect_kind_and_product(name: str) -> tuple[str, str]:
    """Infer (product_code, kind) from the NOSP filename pattern.

    Patterns:
      '서칭뷰_회차별입찰정보*.csv'  -> SEARCHING_VIEW, bid_info
      '서칭뷰_키워드그룹별최근낙찰가*.csv' -> SEARCHING_VIEW, winning
      '신제품_회차별입찰정보*.csv'  -> NEW_PRODUCT, bid_info
      '신제품_키워드그룹별최근낙찰가*.csv' -> NEW_PRODUCT, winning
    """
    n = name
    product = (
        "SEARCHING_VIEW" if n.startswith("서칭뷰_") else "NEW_PRODUCT" if n.startswith("신제품_") else None
    )
    kind = (
        "bid_info" if "회차별입찰정보" in n
        else "winning" if "키워드그룹별최근낙찰가" in n
        else None
    )
    if product is None or kind is None:
        raise ValueError(f"could not classify file: {name}")
    return product, kind


def ingest_one(path: Path, product: str | None = None, kind: str | None = None) -> None:
    if product is None or kind is None:
        product, kind = _detect_kind_and_product(path.name)
    with connect() as conn:
        result = ingest_csv(conn, path=path, product_code=product, kind=kind)
        conn.commit()
        log.info(
            "ingest done",
            file=str(path),
            product=product,
            kind=kind,
            total=result.rows_total,
            inserted=result.rows_inserted,
            updated=result.rows_updated,
        )


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=Path, help="single CSV to ingest")
    parser.add_argument("--product", choices=["SEARCHING_VIEW", "NEW_PRODUCT"])
    parser.add_argument("--kind", choices=["bid_info", "winning"])
    parser.add_argument(
        "--watch", action="store_true", help="watch inbox/ folder (Task 20)"
    )
    args = parser.parse_args(argv)

    if args.watch:
        from worker.watcher import watch_inbox  # local import — Task 20

        watch_inbox(Path("inbox"))
        return 0

    if not args.file:
        parser.error("--file is required when not --watch")

    ingest_one(args.file, args.product, args.kind)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Smoke-test the CLI with a fixture**

Run:

```powershell
cd worker
uv run python -m worker.jobs.csv_ingest --file tests\fixtures\sample_bid_info_searching.csv --product SEARCHING_VIEW --kind bid_info
cd ..
```

Expected: log lines ending in `ingest done ... total=3 inserted=... updated=...`. No exception.

⚠ This writes to the **real Neon database**. That is intentional for the smoke test.

After running, verify via Drizzle Studio:

```powershell
pnpm --filter dashboard drizzle:studio
```

In `rounds` you should see `202622`, `202623`, `202624` rows for `product_id` = `SEARCHING_VIEW`. In `round_keyword_groups` you should see 3 rows referencing `실비보험`. Close studio with Ctrl+C.

- [ ] **Step 4: Clean up the smoke-test rows so future tests are not polluted**

Run:

```powershell
cd worker
uv run python -c "from worker.db import connect; conn = connect().__enter__(); cur = conn.cursor(); cur.execute(\"DELETE FROM ingest_runs\"); cur.execute(\"DELETE FROM round_keyword_groups\"); cur.execute(\"DELETE FROM round_keywords\"); cur.execute(\"DELETE FROM rounds\"); cur.execute(\"DELETE FROM keyword_groups\"); cur.execute(\"DELETE FROM categories\"); conn.commit(); print('cleaned')"
cd ..
```

Expected: prints `cleaned`. `products` rows are preserved.

- [ ] **Step 5: Commit**

```powershell
git add worker/src/worker/jobs
git commit -m "feat(worker): csv_ingest CLI entry point (JOB 2)"
```

---

## Task 20: Inbox folder watcher

**Files:**
- Create: `worker/src/worker/watcher.py`
- Create: `worker/tests/test_watcher.py`

- [ ] **Step 1: Write failing watcher test using a manual event push**

Create file `worker/tests/test_watcher.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock

from worker.watcher import _IngestHandler


def test_handler_dispatches_only_matching_csv_files(tmp_path: Path):
    ingest = MagicMock()
    handler = _IngestHandler(ingest_fn=ingest)

    # matching name
    good = tmp_path / "서칭뷰_회차별입찰정보.csv"
    good.write_text("dummy", encoding="utf-8")
    handler._handle(str(good))

    # non-csv
    bad = tmp_path / "notes.txt"
    bad.write_text("dummy", encoding="utf-8")
    handler._handle(str(bad))

    # unrelated csv pattern
    other = tmp_path / "random.csv"
    other.write_text("dummy", encoding="utf-8")
    handler._handle(str(other))

    assert ingest.call_count == 1
    assert ingest.call_args.args[0] == good
```

- [ ] **Step 2: Verify it fails**

Run:

```powershell
cd worker
uv run pytest tests/test_watcher.py -v
cd ..
```

Expected: ImportError.

- [ ] **Step 3: Implement the watcher**

Create file `worker/src/worker/watcher.py`:

```python
"""Inbox/ folder watcher (manual drop fallback — path A of B→C→A cascade)."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from worker.logging import get_logger

log = get_logger(__name__)

_KNOWN_PATTERNS = ("서칭뷰_", "신제품_")
_RAW_ROOT = Path("raw")


def _looks_like_nosp_csv(name: str) -> bool:
    return name.lower().endswith(".csv") and name.startswith(_KNOWN_PATTERNS)


def _archive(path: Path) -> Path:
    today = date.today().isoformat()
    dest_dir = _RAW_ROOT / today
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    shutil.move(str(path), str(dest))
    return dest


class _IngestHandler(FileSystemEventHandler):
    def __init__(self, ingest_fn: Callable[[Path], None]) -> None:
        self._ingest = ingest_fn

    def on_created(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        self._handle(event.src_path)

    def on_moved(self, event):  # type: ignore[override]
        if event.is_directory:
            return
        self._handle(event.dest_path)

    def _handle(self, src_path: str) -> None:
        path = Path(src_path)
        if not _looks_like_nosp_csv(path.name):
            return
        # Wait briefly to let the file fully flush
        time.sleep(0.5)
        archived = _archive(path)
        try:
            self._ingest(archived)
        except Exception:
            log.exception("ingest failed", file=str(archived))


def watch_inbox(inbox: Path) -> None:
    inbox.mkdir(parents=True, exist_ok=True)
    from worker.jobs.csv_ingest import ingest_one  # local to avoid cycle

    handler = _IngestHandler(ingest_fn=ingest_one)
    observer = Observer()
    observer.schedule(handler, str(inbox), recursive=False)
    observer.start()
    log.info("watching inbox", path=str(inbox))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

- [ ] **Step 4: Run watcher test**

Run:

```powershell
cd worker
uv run pytest tests/test_watcher.py -v
cd ..
```

Expected: PASS.

- [ ] **Step 5: Live smoke-test the watcher**

Open one terminal:

```powershell
cd C:\Users\MADUP\Documents\SearchingviewNewProduct
uv run --project worker python -m worker.jobs.csv_ingest --watch
```

It prints `watching inbox path=inbox`.

In a **second** terminal:

```powershell
copy worker\tests\fixtures\sample_bid_info_searching.csv inbox\서칭뷰_회차별입찰정보_smoke.csv
```

The first terminal should log `ingest done ...` within ~2 seconds, and the file should have been moved into `raw/<today>/`.

Stop the watcher with Ctrl+C.

- [ ] **Step 6: Clean up smoke-test rows again**

Run:

```powershell
cd worker
uv run python -c "from worker.db import connect; conn = connect().__enter__(); cur = conn.cursor(); [cur.execute(f'DELETE FROM {t}') for t in ('ingest_runs','round_keyword_groups','round_keywords','rounds','keyword_groups','categories')]; conn.commit(); print('cleaned')"
cd ..
```

- [ ] **Step 7: Commit**

```powershell
git add worker/src/worker/watcher.py worker/tests/test_watcher.py
git commit -m "feat(worker): inbox folder watcher dispatching NOSP CSVs"
```

---

## Task 21: Full real-data dry run with all 4 NOSP CSVs

**Files:**
- (none — runtime verification only)

- [ ] **Step 1: Place real CSVs in `inbox/`**

Use your real downloads. Rename them so the watcher classifier picks them up correctly. From the user-provided downloads they are already named:

```
신제품_회차별입찰정보 (14).csv
신제품_키워드그룹별최근낙찰가 (15).csv
```

Add the two 서칭뷰 versions if available. Copy all of them to `inbox/`:

```powershell
copy "$env:USERPROFILE\Downloads\신제품_회차별입찰정보 (14).csv" inbox\
copy "$env:USERPROFILE\Downloads\신제품_키워드그룹별최근낙찰가 (15).csv" inbox\
```

- [ ] **Step 2: Run the watcher**

```powershell
uv run --project worker python -m worker.jobs.csv_ingest --watch
```

Expected: each file logged with `ingest done ... total=<N>` lines. No exceptions. Files end up under `raw/<today>/`.

Stop with Ctrl+C.

- [ ] **Step 3: Verify counts in DB**

Run:

```powershell
cd worker
uv run python -c "from worker.db import connect; conn = connect().__enter__(); cur = conn.cursor(); cur.execute('SELECT p.code, COUNT(rkg.*) FROM round_keyword_groups rkg JOIN rounds r ON r.id = rkg.round_id JOIN products p ON p.id = r.product_id GROUP BY p.code'); print(cur.fetchall())"
cd ..
```

Expected: a list with positive counts per product, e.g. `[('NEW_PRODUCT', 487), ('SEARCHING_VIEW', 412)]` (exact numbers vary).

- [ ] **Step 4: Spot-check the winning bid attachment**

Run:

```powershell
cd worker
uv run python -c "from worker.db import connect; conn = connect().__enter__(); cur = conn.cursor(); cur.execute(\"SELECT kg.name, r.round_no, rkg.regular_winning_bid FROM round_keyword_groups rkg JOIN rounds r ON r.id = rkg.round_id JOIN keyword_groups kg ON kg.id = rkg.keyword_group_id WHERE rkg.regular_winning_bid IS NOT NULL ORDER BY r.round_no DESC LIMIT 10\"); [print(row) for row in cur.fetchall()]"
cd ..
```

Expected: 10 rows with non-null winning bids. Spot-check that the round numbers correspond to the most recently announced rounds.

- [ ] **Step 5: Document the smoke test result**

In `README.md`, add a section:

```markdown

## W1 dry-run result

Ran end-to-end ingest on YYYY-MM-DD with NOSP CSVs:
- SEARCHING_VIEW: <N> round_keyword_groups
- NEW_PRODUCT: <N> round_keyword_groups
- Winning bids attached: <N> rows

See `raw/<date>/` for the source files.
```

Replace the placeholders with the actual numbers from steps 3-4.

- [ ] **Step 6: Commit**

```powershell
git add README.md
git commit -m "docs: log W1 dry-run result"
```

---

## Task 22: Lint, test, and document the worker

**Files:**
- (none — verification)

- [ ] **Step 1: Run full test suite**

```powershell
cd worker
uv run pytest -v
cd ..
```

Expected: every test passes. Tests marked `@pytest.mark.db` need `DATABASE_URL` set, which it is via `.env.local`.

- [ ] **Step 2: Run linter**

```powershell
cd worker
uv run ruff check .
uv run ruff format --check .
cd ..
```

Expected: 0 warnings/errors. If `ruff format --check` reports issues, fix them with `uv run ruff format .` and recommit.

- [ ] **Step 3: Verify TypeScript build of dashboard still compiles**

```powershell
pnpm --filter dashboard build
```

Expected: build completes with `Compiled successfully`. (Dashboard is still the W1 placeholder homepage — that is fine.)

- [ ] **Step 4: Write a one-page operator note**

Create file `worker/README.md`:

```markdown
# Worker

Python 3.13 + uv. Owns CSV ingest, NOSP scraping, brand scraping, Sheets sync.

## Setup

1. Install uv: `pip install uv`
2. `cp .env.example .env.local` and fill in `DATABASE_URL` (Neon pooled URL).
3. `uv sync`

## JOB 2 — CSV ingest (W1)

Single file:

```bash
uv run python -m worker.jobs.csv_ingest --file path/to/file.csv --product SEARCHING_VIEW --kind bid_info
```

Watch mode (`inbox/` folder, manual-drop fallback):

```bash
uv run python -m worker.jobs.csv_ingest --watch
```

Filename auto-classification: any CSV starting with `서칭뷰_` or `신제품_` and containing either `회차별입찰정보` or `키워드그룹별최근낙찰가` is recognized.

Processed files are archived to `raw/YYYY-MM-DD/` and a row is written to `ingest_runs`.

## Tests

```bash
uv run pytest          # all
uv run pytest -m db    # only db-touching tests
```

`db_conn` fixture in `tests/conftest.py` opens a Neon transaction and rolls it back at teardown, so tests do not pollute production data.
```

- [ ] **Step 5: Commit and tag W1 complete**

```powershell
git add worker/README.md
git commit -m "docs: operator note for worker"
git tag w1-complete
```

Expected: tag created. `git log --oneline w1-complete` shows the chain of W1 commits.

---

## W1 Acceptance Criteria

- [ ] Neon Postgres project exists; `DATABASE_URL` is in two gitignored `.env.local` files
- [ ] Drizzle schema has 10 tables; `pnpm --filter dashboard drizzle:migrate` is a no-op (schema in sync)
- [ ] `products` is seeded with `SEARCHING_VIEW` and `NEW_PRODUCT`
- [ ] `worker/tests` has 13+ tests passing, including 9+ `db`-marked tests
- [ ] CLI `python -m worker.jobs.csv_ingest --watch` ingests real NOSP CSVs end-to-end
- [ ] `ruff check` and `ruff format --check` both clean
- [ ] `pnpm --filter dashboard build` succeeds
- [ ] `git tag w1-complete` exists

---

## Self-Review Notes

Spec coverage:

- §3 data model — Tasks 5–9 (all 10 tables)
- §4.1 JOB 2 — Tasks 13, 15–19
- §4.2 manual-drop fallback — Task 20 (inbox watcher)
- §9 backfill mode — `--file` CLI is the same code path as `--backfill` would be; a flag will be added when real backfill files arrive in W2

Not in W1 (deferred to later milestones):

- JOB 1 (NOSP auto-download) → W3
- JOB 3 (brand scrape) → W4
- JOB 4 (Sheets sync) → W5
- Dashboard screens 1–4 → W2–W5
- Cloudflare Pages deploy → W5
- Slack notifications → W5

Type consistency check: `IngestResult` fields (`rows_total`, `rows_inserted`, `rows_updated`, `run_id`) match the SQL columns in `ingest_runs` (rows_total, rows_inserted, rows_updated, id). Schema field names match between Drizzle (`regularWinningBid`) and Python (`regular_winning_bid` column) — Drizzle's camelCase TypeScript names map to snake_case columns via the `column("snake")` overrides. All upsert function signatures used in `ingest.py` exist in `upsert.py`.

Placeholder scan: none. Every step has a concrete command or code block.
