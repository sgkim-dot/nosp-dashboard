# W2 — Backfill & Bid-Decision Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backfill all 72 historical NOSP CSVs from the user's Downloads folder into Neon, then build Screen 1 (입찰 의사결정 — keyword-group level trend chart, round table, and insights) in Next.js with real data driving every pixel.

**Architecture:** Phase A extends the existing worker JOB 2 with a `--backfill` mode that walks a directory, classifies files, sorts them safely (bid_info before winning, within each product, ordered by the `(N)` suffix), and ingests sequentially. Phase B replaces the placeholder home page with a server-rendered decision screen — Drizzle queries on the server, cascading filters in URL search params, shadcn/ui primitives, and Recharts for the line chart.

**Tech Stack:** Python 3.13+ (worker), psycopg, Next.js 16, React 19, TypeScript, Drizzle ORM, @neondatabase/serverless, Tailwind 4, shadcn/ui, Recharts, lucide-react.

**Spec reference:** [2026-05-19-nosp-dashboard-design.md](../specs/2026-05-19-nosp-dashboard-design.md) sections 5.1, 9, 10 (W2).

**Builds on:** [2026-05-19-w1-db-and-csv-ingest.md](2026-05-19-w1-db-and-csv-ingest.md) — tag `w1-complete`.

---

## File Structure

After W2 the new/changed files are:

```
worker/
├─ src/worker/
│  ├─ backfill.py                       # NEW: directory walker + safe ordering
│  └─ jobs/csv_ingest.py                # MODIFIED: add --backfill <dir>
└─ tests/
   ├─ fixtures/backfill/                # NEW: tiny set of multi-product CSVs
   │  ├─ 서칭뷰_회차별입찰정보 (1).csv
   │  ├─ 서칭뷰_회차별입찰정보 (2).csv
   │  ├─ 서칭뷰_키워드그룹별최근낙찰가 (2).csv
   │  └─ 신제품_회차별입찰정보 (1).csv
   └─ test_backfill.py                  # NEW

apps/dashboard/
├─ components.json                       # NEW: shadcn config
├─ app/
│  ├─ layout.tsx                        # MODIFIED: add sidebar shell
│  ├─ globals.css                       # MODIFIED: shadcn CSS vars
│  ├─ page.tsx                          # REPLACED: Screen 1
│  └─ favicon.ico                       # (untouched)
├─ components/
│  ├─ ui/                               # NEW: shadcn primitives (only what we use)
│  │  ├─ button.tsx
│  │  ├─ card.tsx
│  │  ├─ select.tsx
│  │  ├─ separator.tsx
│  │  └─ table.tsx
│  ├─ layout/
│  │  └─ sidebar.tsx                    # NEW
│  └─ bid-decision/
│     ├─ filter-bar.tsx                 # NEW: 5-way cascading filter
│     ├─ summary-card.tsx               # NEW: top-of-screen kpis
│     ├─ trend-chart.tsx                # NEW: Recharts line
│     ├─ round-table.tsx                # NEW
│     └─ insights-card.tsx              # NEW
├─ lib/
│  ├─ db/
│  │  ├─ queries.ts                     # NEW: typed DB queries used by Screen 1
│  │  └─ schema/...                     # (existing, unchanged)
│  ├─ utils.ts                          # NEW: cn() helper for class merging
│  └─ format.ts                         # NEW: KRW + ratio formatters
└─ types/
   └─ bid-decision.ts                   # NEW: shared types between server + components
```

---

# PHASE A — Backfill

## Task 1: Add `--backfill <dir>` to the CSV ingest CLI (skeleton + arg parsing)

**Files:**
- Modify: `worker/src/worker/jobs/csv_ingest.py`

- [ ] **Step 1: Read the current CLI to understand its current structure**

Run: `cd worker && cat src/worker/jobs/csv_ingest.py`

Confirm it currently has `--file`, `--product`, `--kind`, `--watch` args.

- [ ] **Step 2: Add `--backfill <DIR>` argparse option**

Modify `worker/src/worker/jobs/csv_ingest.py`. In the `main()` function, after the existing `parser.add_argument(...)` calls and before `args = parser.parse_args(argv)`, add:

```python
    parser.add_argument(
        "--backfill",
        type=Path,
        metavar="DIR",
        help="batch-ingest all NOSP CSVs in DIR in safe order",
    )
```

Then, just after `args = parser.parse_args(argv)`, add the dispatch:

```python
    if args.backfill:
        from worker.backfill import backfill_directory

        backfill_directory(args.backfill)
        return 0
```

The `--watch` and `--file` branches remain unchanged. The `--backfill` branch takes precedence over `--file`.

- [ ] **Step 3: Sanity-check the CLI still parses**

```
cd worker
uv run python -m worker.jobs.csv_ingest --help
```

Expected output includes the `--backfill DIR` line.

- [ ] **Step 4: Commit**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git add worker/src/worker/jobs/csv_ingest.py
git commit -m "feat(worker): add --backfill flag to csv_ingest CLI"
```

---

## Task 2: Write `backfill.py` (TDD)

**Files:**
- Create: `worker/src/worker/backfill.py`
- Create: `worker/tests/test_backfill.py`
- Create: `worker/tests/fixtures/backfill/` with 4 CSV fixtures

**Behavior to implement:**
- Walk a directory non-recursively for `*.csv` files.
- Classify each via the existing `_detect_kind_and_product()` from `worker.jobs.csv_ingest`.
- Skip files that don't match the NOSP naming pattern (log a warning).
- Sort the matched files: **all `bid_info` files of all products before any `winning` file**, and within each `(product, kind)` group sort by filename ascending (so `(1).csv` precedes `(10).csv`; use `natsort`-style numeric tail sort).
- For each file: call `ingest_one()` from `worker.jobs.csv_ingest`. After successful ingest, move the source file to `raw/<today>/`. On failure, log the exception but continue with the next file.
- Print a summary at the end: `{success_count, error_count, skipped_count}`.

- [ ] **Step 1: Create fixture directory**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
mkdir -p worker/tests/fixtures/backfill
```

- [ ] **Step 2: Copy existing sample CSVs into 4 numbered variants**

Use the Write tool to create these 4 files under `worker/tests/fixtures/backfill/`. Each file body is **identical** to the W1 fixture of the same kind+product, but the keyword_group line must use a unique synthetic name `__bf_테스트__` so we never collide with real data.

File `worker/tests/fixtures/backfill/서칭뷰_회차별입찰정보 (1).csv`:

```

서칭뷰 키워드그룹 : 회차별 입찰 정보
조회일자:20260512

집행회차,집행기간,대분류,소분류,키워드그룹,기준조회수,최저입찰가,정기입찰기간,정기입찰발표,재입찰기간,재입찰발표,입찰가능여부,현재공실구좌
202621,20260518~20260524,금융,금융상품,__bf_테스트__,12000,500000,20260421~20260504,20260505,20260506~20260511,20260512,입찰기간종료,0
```

File `worker/tests/fixtures/backfill/서칭뷰_회차별입찰정보 (2).csv`:

```

서칭뷰 키워드그룹 : 회차별 입찰 정보
조회일자:20260519

집행회차,집행기간,대분류,소분류,키워드그룹,기준조회수,최저입찰가,정기입찰기간,정기입찰발표,재입찰기간,재입찰발표,입찰가능여부,현재공실구좌
202622,20260525~20260531,금융,금융상품,__bf_테스트__,12500,520000,20260428~20260511,20260512,20260513~20260518,20260519,입찰기간종료,0
```

File `worker/tests/fixtures/backfill/서칭뷰_키워드그룹별최근낙찰가 (2).csv`:

```

서칭뷰 키워드그룹 : 최근낙찰가
조회일자:20260519

대분류,소분류,키워드그룹,최근낙찰가
금융,금융상품,__bf_테스트__,540000
```

File `worker/tests/fixtures/backfill/신제품_회차별입찰정보 (1).csv`:

```

신제품검색 키워드그룹 : 회차별 입찰 정보
조회일자:20260519

집행회차,집행기간,대분류,소분류,키워드그룹,기준조회수,최저입찰가,정기입찰기간,정기입찰발표,재입찰기간,재입찰발표,입찰가능여부,현재공실구좌
202622,20260525~20260531,가구/인테리어,거실가구,__bf_테스트__,2000,250000,20260428~20260511,20260512,20260513~20260518,20260519,입찰기간종료,0
```

- [ ] **Step 3: Write failing tests `worker/tests/test_backfill.py`**

```python
from pathlib import Path
from unittest.mock import patch

import pytest

from worker.backfill import classify_and_sort, backfill_directory

FIXTURES = Path(__file__).parent / "fixtures" / "backfill"


def test_classify_and_sort_groups_bid_info_before_winning(tmp_path: Path):
    # Mirror the fixture dir into tmp_path so we don't move real fixtures
    for f in FIXTURES.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes())

    sorted_paths = classify_and_sort(tmp_path)

    # All bid_info first, then winning
    kinds = [p.kind for p in sorted_paths]
    bi_indices = [i for i, k in enumerate(kinds) if k == "bid_info"]
    w_indices = [i for i, k in enumerate(kinds) if k == "winning"]
    assert max(bi_indices) < min(w_indices)


def test_classify_and_sort_numeric_filename_order(tmp_path: Path):
    for f in FIXTURES.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes())

    sorted_paths = classify_and_sort(tmp_path)
    sv_bid = [p.path.name for p in sorted_paths if p.product == "SEARCHING_VIEW" and p.kind == "bid_info"]
    # (1) must come before (2)
    assert sv_bid == ["서칭뷰_회차별입찰정보 (1).csv", "서칭뷰_회차별입찰정보 (2).csv"]


def test_classify_and_sort_skips_unknown_files(tmp_path: Path):
    for f in FIXTURES.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes())
    (tmp_path / "random.csv").write_text("nope", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("nope", encoding="utf-8")

    sorted_paths = classify_and_sort(tmp_path)
    names = [p.path.name for p in sorted_paths]
    assert "random.csv" not in names
    assert "notes.txt" not in names
    assert len(sorted_paths) == 4


@pytest.mark.db
def test_backfill_directory_ingests_in_order(tmp_path: Path):
    for f in FIXTURES.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes())

    calls: list[tuple[str, str]] = []

    def fake_ingest_one(path: Path, product=None, kind=None):
        if product is None or kind is None:
            from worker.jobs.csv_ingest import _detect_kind_and_product
            product, kind = _detect_kind_and_product(path.name)
        calls.append((path.name, kind))

    with patch("worker.backfill.ingest_one", side_effect=fake_ingest_one):
        result = backfill_directory(tmp_path, archive=False)

    assert result.success == 4
    assert result.error == 0
    assert result.skipped == 0
    # First call must be a bid_info, last call must be a winning
    assert calls[0][1] == "bid_info"
    assert calls[-1][1] == "winning"
```

- [ ] **Step 4: Verify tests fail (ImportError)**

```
cd worker
uv run pytest tests/test_backfill.py -v
```

Expected: import error / collection failure (`worker.backfill` does not exist yet).

- [ ] **Step 5: Implement `worker/src/worker/backfill.py`**

```python
"""Directory walker + safe-order driver for batch CSV ingest (JOB 2 backfill)."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from worker.jobs.csv_ingest import _detect_kind_and_product, ingest_one
from worker.logging import get_logger

log = get_logger(__name__)

_NUM_TAIL = re.compile(r" \((\d+)\)(?=\.[^.]+$)")
_RAW_ROOT = Path("raw")


@dataclass(frozen=True)
class ClassifiedFile:
    path: Path
    product: str  # "SEARCHING_VIEW" | "NEW_PRODUCT"
    kind: str  # "bid_info" | "winning"


@dataclass
class BackfillResult:
    success: int = 0
    error: int = 0
    skipped: int = 0


def _natural_key(path: Path) -> tuple[int, str]:
    """Sort key that treats the ' (N)' suffix as numeric.

    'foo.csv'      -> (0, 'foo.csv')
    'foo (1).csv'  -> (1, 'foo (1).csv')
    'foo (10).csv' -> (10, 'foo (10).csv')
    """
    m = _NUM_TAIL.search(path.name)
    n = int(m.group(1)) if m else 0
    return (n, path.name)


def classify_and_sort(directory: Path) -> list[ClassifiedFile]:
    out: list[ClassifiedFile] = []
    for p in sorted(directory.iterdir()):
        if not p.is_file() or p.suffix.lower() != ".csv":
            continue
        try:
            product, kind = _detect_kind_and_product(p.name)
        except ValueError:
            log.warning("skipping unrecognized file", file=p.name)
            continue
        out.append(ClassifiedFile(path=p, product=product, kind=kind))

    # Order: kind asc (bid_info < winning), then product asc, then natural filename.
    kind_rank = {"bid_info": 0, "winning": 1}
    return sorted(
        out,
        key=lambda cf: (kind_rank[cf.kind], cf.product, _natural_key(cf.path)),
    )


def _archive(path: Path) -> Path:
    today = date.today().isoformat()
    dest_dir = _RAW_ROOT / today
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    shutil.move(str(path), str(dest))
    return dest


def backfill_directory(directory: Path, *, archive: bool = True) -> BackfillResult:
    result = BackfillResult()
    classified = classify_and_sort(directory)

    # Count skipped: any csv in dir not in classified
    all_csvs = sum(1 for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".csv")
    result.skipped = all_csvs - len(classified)

    log.info(
        "backfill starting",
        directory=str(directory),
        total=len(classified),
        skipped=result.skipped,
    )

    for cf in classified:
        try:
            ingest_one(cf.path, product=cf.product, kind=cf.kind)
            if archive:
                _archive(cf.path)
            result.success += 1
        except Exception as exc:
            log.exception("backfill file failed", file=cf.path.name, error=str(exc))
            result.error += 1

    log.info(
        "backfill done",
        success=result.success,
        error=result.error,
        skipped=result.skipped,
    )
    return result
```

- [ ] **Step 6: Run tests — expect 4 pass**

```
cd worker
uv run pytest tests/test_backfill.py -v
```

Expected: 4 passed (3 unit tests + 1 db-marked test that uses a patched ingest_one so it never hits the DB despite the `db` mark — the mark is there only so the test runs in the same group as other db tests; functionally it's a unit test).

⚠ If the db-marked test fails because `db_conn` autouse interferes, drop the `@pytest.mark.db` decorator on `test_backfill_directory_ingests_in_order` — it doesn't need a DB.

- [ ] **Step 7: Run full suite — expect 19 pass total**

```
cd worker
uv run pytest -v
```

Expected: 15 (W1) + 4 (W2 Task 2) = 19.

- [ ] **Step 8: Commit**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git add worker/src/worker/backfill.py worker/tests/test_backfill.py worker/tests/fixtures/backfill
git commit -m "feat(worker): backfill mode with safe ordering and TDD coverage"
```

---

## Task 3: Run the real backfill on user's 72 historical CSVs

**Files:**
- (no source changes — this is a runtime task)
- Will write data to `raw/<today>/` and Neon

- [ ] **Step 1: Prepare a staging directory**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
mkdir -p backfill-staging
cp "/c/Users/MADUP/Downloads/"서칭뷰_*.csv backfill-staging/ 2>/dev/null || true
cp "/c/Users/MADUP/Downloads/"신제품_*.csv backfill-staging/ 2>/dev/null || true
ls backfill-staging/ | wc -l
```

Expected: 70+ files copied (72 minus any `회차별키워드셋` files we don't yet support; those will be skipped with warnings — that's fine).

- [ ] **Step 2: Snapshot the pre-backfill DB state**

```
cd worker
uv run python -c "
import psycopg
from worker.config import load_settings
s = load_settings()
with psycopg.connect(s.database_url) as conn:
    cur = conn.cursor()
    for tbl in ['products','categories','keyword_groups','rounds','round_keyword_groups','ingest_runs']:
        cur.execute(f'SELECT COUNT(*) FROM {tbl}')
        print(f'{tbl}: {cur.fetchone()[0]}')
"
```

Record these numbers — they should grow after the backfill.

- [ ] **Step 3: Run the backfill**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
uv run --project worker python -m worker.jobs.csv_ingest --backfill backfill-staging 2>&1 | tee backfill.log
```

Expected: ~70 `ingest done ...` lines, ending with `backfill done success=N error=0 skipped=M`. The whole run will take ~30 min for 70 files because each file triggers many DB roundtrips through the pooled Neon connection. **Don't interrupt** — let it finish or fail naturally.

⚠ If it looks stuck (no log line for >5 min on a single file), capture: `ps`, the current file name from the last log line, and report — don't kill blindly. Likely cause if it stalls: a CSV with unexpected column count (a brand-new NOSP variant). Look for `IndexError` in the log.

- [ ] **Step 4: Post-backfill DB snapshot**

```
cd worker
uv run python -c "
import psycopg
from worker.config import load_settings
s = load_settings()
with psycopg.connect(s.database_url) as conn:
    cur = conn.cursor()
    for tbl in ['products','categories','keyword_groups','rounds','round_keyword_groups','ingest_runs']:
        cur.execute(f'SELECT COUNT(*) FROM {tbl}')
        print(f'{tbl}: {cur.fetchone()[0]}')
    cur.execute('SELECT MIN(round_no), MAX(round_no) FROM rounds')
    print('round range:', cur.fetchone())
    cur.execute('SELECT COUNT(*) FROM round_keyword_groups WHERE regular_winning_bid IS NOT NULL')
    print('winning bids attached:', cur.fetchone()[0])
"
```

Expected: rounds count significantly higher (the 72 weekly CSVs ≈ 11 weeks × 2 products = 22+ rounds), `keyword_groups` in the low thousands, winning bids attached for the announced rounds.

- [ ] **Step 5: Verify no ingest_runs error rows**

```
cd worker
uv run python -c "
import psycopg
from worker.config import load_settings
s = load_settings()
with psycopg.connect(s.database_url) as conn:
    cur = conn.cursor()
    cur.execute(\"SELECT run_type, status, file_path, error_message FROM ingest_runs WHERE status='error'\")
    rows = cur.fetchall()
    print('error runs:', len(rows))
    for r in rows: print(r)
"
```

Expected: `error runs: 0`. If non-zero, list the failing files and decide whether to fix the parser (new task) or skip those files for now.

- [ ] **Step 6: Append to root `README.md`**

In the "W1 dry-run result" section already added, append a new sub-section:

```markdown
### W2 backfill result (2026-05-20)

Ingested N historical NOSP CSVs:
- Rounds: <min>~<max>
- round_keyword_groups: <count>
- Winning bids attached: <count>
- 0 ingest errors

Source CSVs archived to `raw/<date>/`. Staging directory `backfill-staging/` is gitignored.
```

Fill in the actual numbers from Steps 4–5.

- [ ] **Step 7: Add `backfill-staging/` and `backfill.log` to `.gitignore`**

Edit root `.gitignore` and add:

```
# Backfill workspace
backfill-staging/
backfill.log
```

- [ ] **Step 8: Commit the readme + gitignore changes**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git add README.md .gitignore
git commit -m "docs: log W2 backfill result and ignore staging dirs"
```

---

# PHASE B — Screen 1 (Bid Decision Support)

## Task 4: Install UI dependencies (shadcn/ui + Recharts + lucide-react)

**Files:**
- Modify: `apps/dashboard/package.json`, `apps/dashboard/components.json` (new), `apps/dashboard/lib/utils.ts` (new), `apps/dashboard/app/globals.css`

- [ ] **Step 1: Install runtime deps**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
pnpm --filter dashboard add recharts lucide-react class-variance-authority clsx tailwind-merge
pnpm --filter dashboard add -D @types/node
```

- [ ] **Step 2: Initialize shadcn**

```
cd apps/dashboard
pnpm dlx shadcn@latest init --yes --base-color neutral --css-variables
cd ../..
```

If the CLI complains it doesn't auto-detect Next.js 16, pick the New York style and accept defaults (path: components/ui, tailwind: app/globals.css, alias: @/).

This writes `apps/dashboard/components.json` and may modify `app/globals.css` to add CSS vars and `tailwind.config.*` for shadcn theming.

- [ ] **Step 3: Add the 5 shadcn primitives we'll use**

```
cd apps/dashboard
pnpm dlx shadcn@latest add button card select separator table --yes
cd ../..
```

Expected: 5 files appear under `apps/dashboard/components/ui/`.

- [ ] **Step 4: Confirm `apps/dashboard/lib/utils.ts` exists with `cn()` helper**

The shadcn CLI auto-creates this file. Verify with:

```
cat apps/dashboard/lib/utils.ts
```

Expected content (approx):

```ts
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

If the file doesn't exist, create it with that content yourself.

- [ ] **Step 5: Build smoke**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
pnpm --filter dashboard build
```

Expected: build succeeds.

- [ ] **Step 6: Commit**

```
git add apps/dashboard package.json pnpm-lock.yaml
git commit -m "feat(dashboard): install shadcn/ui + Recharts + lucide-react"
```

---

## Task 5: App layout shell (sidebar + page area)

**Files:**
- Modify: `apps/dashboard/app/layout.tsx`
- Create: `apps/dashboard/components/layout/sidebar.tsx`

- [ ] **Step 1: Write `apps/dashboard/components/layout/sidebar.tsx`**

```tsx
import Link from "next/link";
import { Gauge, Calendar, Building2, Settings2 } from "lucide-react";

const NAV = [
  { href: "/", label: "입찰 의사결정", icon: Gauge },
  { href: "/round", label: "회차 현황", icon: Calendar },
  { href: "/brand", label: "브랜드 점유", icon: Building2 },
  { href: "/ops", label: "운영", icon: Settings2 },
];

export function Sidebar() {
  return (
    <aside className="w-56 shrink-0 border-r bg-muted/30 px-3 py-4">
      <div className="px-2 pb-4">
        <div className="text-sm font-semibold tracking-tight">NOSP 입찰</div>
        <div className="text-xs text-muted-foreground">대시보드</div>
      </div>
      <nav className="space-y-1">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-foreground/80 hover:bg-accent hover:text-accent-foreground"
          >
            <Icon className="h-4 w-4" aria-hidden />
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 2: Modify `apps/dashboard/app/layout.tsx`**

Replace the entire file contents with:

```tsx
import type { Metadata } from "next";
import { Sidebar } from "@/components/layout/sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "NOSP 입찰 대시보드",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 overflow-x-hidden">{children}</main>
        </div>
      </body>
    </html>
  );
}
```

⚠ If the existing `layout.tsx` imports Geist or other fonts that the create-next-app added, keep those imports and apply the className to `<body>`. Adapt as needed but the layout shape (`flex` + Sidebar + main) must match.

- [ ] **Step 3: Verify dev server renders**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
pnpm --filter dashboard dev
```

Open http://localhost:3000. Expected: left sidebar with 4 links, main area still shows the placeholder home. Stop server (Ctrl+C).

- [ ] **Step 4: Commit**

```
git add apps/dashboard/app/layout.tsx apps/dashboard/components/layout
git commit -m "feat(dashboard): app shell with sidebar"
```

---

## Task 6: DB query layer + shared types

**Files:**
- Create: `apps/dashboard/types/bid-decision.ts`
- Create: `apps/dashboard/lib/db/queries.ts`
- Create: `apps/dashboard/lib/format.ts`

- [ ] **Step 1: Write `apps/dashboard/types/bid-decision.ts`**

```ts
export type ProductCode = "SEARCHING_VIEW" | "NEW_PRODUCT";

export type FilterState = {
  product: ProductCode;
  categoryLvl1: string | null;
  categoryLvl2: string | null;
  keywordGroupId: number | null;
  lastNRounds: number; // default 12
};

export type RoundRow = {
  roundId: number;
  roundNo: number;
  periodStart: string; // ISO date
  periodEnd: string;
  minBidPrice: number | null;
  regularWinningBid: number | null;
  emptySlots: number | null;
  bidStatus: string | null;
  ratio: number | null; // winning / min (null if winning missing)
};

export type KeywordGroupSummary = {
  keywordGroupId: number;
  keywordGroupName: string;
  product: ProductCode;
  categoryLvl1: string;
  categoryLvl2: string;
  latestWinning: number | null;
  latestEmptySlots: number | null;
  rounds: RoundRow[];
};

export type Insights = {
  meanRatio: number | null;        // mean winning/min over rounds with winning
  vacancyRate: number | null;      // share of rounds with emptySlots>0
  recommendedLow: number | null;   // ~p20 ratio × current min
  recommendedHigh: number | null;  // ~p80 ratio × current min
};
```

- [ ] **Step 2: Write `apps/dashboard/lib/format.ts`**

```ts
export function formatKRW(value: number | null | undefined): string {
  if (value == null) return "-";
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}k`;
  return String(value);
}

export function formatRatio(ratio: number | null | undefined): string {
  if (ratio == null) return "-";
  return `${ratio.toFixed(2)}x`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  return iso.slice(5).replace("-", ".");
}
```

- [ ] **Step 3: Write `apps/dashboard/lib/db/queries.ts`**

```ts
import "server-only";
import { and, asc, desc, eq, isNotNull, sql } from "drizzle-orm";
import { createDb } from "./client";
import {
  categories,
  keywordGroups,
  products,
  roundKeywordGroups,
  rounds,
} from "./schema";
import type {
  Insights,
  KeywordGroupSummary,
  ProductCode,
  RoundRow,
} from "@/types/bid-decision";

const db = createDb();

export async function getProducts() {
  return db.select().from(products).orderBy(asc(products.id));
}

export async function getCategoriesLvl1() {
  const rows = await db
    .select({ id: categories.id, name: categories.name })
    .from(categories)
    .where(eq(categories.level, 1))
    .orderBy(asc(categories.name));
  return rows;
}

export async function getCategoriesLvl2(lvl1Name: string) {
  const rows = await db.execute(sql`
    SELECT c2.id, c2.name
    FROM categories c1
    JOIN categories c2 ON c2.parent_id = c1.id AND c2.level = 2
    WHERE c1.level = 1 AND c1.name = ${lvl1Name}
    ORDER BY c2.name
  `);
  return rows.rows as { id: number; name: string }[];
}

export async function getKeywordGroups(args: {
  product: ProductCode;
  categoryLvl1: string | null;
  categoryLvl2: string | null;
}) {
  const rows = await db.execute(sql`
    SELECT kg.id, kg.name
    FROM keyword_groups kg
    JOIN products p ON p.id = kg.product_id
    JOIN categories c2 ON c2.id = kg.category_id
    JOIN categories c1 ON c1.id = c2.parent_id
    WHERE p.code = ${args.product}
      ${args.categoryLvl1 ? sql`AND c1.name = ${args.categoryLvl1}` : sql``}
      ${args.categoryLvl2 ? sql`AND c2.name = ${args.categoryLvl2}` : sql``}
    ORDER BY kg.name
    LIMIT 500
  `);
  return rows.rows as { id: number; name: string }[];
}

export async function getKeywordGroupSummary(args: {
  keywordGroupId: number;
  lastNRounds: number;
}): Promise<KeywordGroupSummary | null> {
  const head = await db.execute(sql`
    SELECT
      kg.id AS keyword_group_id,
      kg.name AS keyword_group_name,
      p.code AS product,
      c1.name AS category_lvl1,
      c2.name AS category_lvl2
    FROM keyword_groups kg
    JOIN products p ON p.id = kg.product_id
    JOIN categories c2 ON c2.id = kg.category_id
    JOIN categories c1 ON c1.id = c2.parent_id
    WHERE kg.id = ${args.keywordGroupId}
  `);
  if (head.rows.length === 0) return null;
  const h = head.rows[0] as {
    keyword_group_id: number;
    keyword_group_name: string;
    product: ProductCode;
    category_lvl1: string;
    category_lvl2: string;
  };

  const tail = await db.execute(sql`
    SELECT
      r.id AS round_id,
      r.round_no,
      r.period_start::text AS period_start,
      r.period_end::text AS period_end,
      rkg.min_bid_price,
      rkg.regular_winning_bid,
      rkg.empty_slots,
      rkg.bid_status
    FROM round_keyword_groups rkg
    JOIN rounds r ON r.id = rkg.round_id
    WHERE rkg.keyword_group_id = ${args.keywordGroupId}
    ORDER BY r.round_no DESC
    LIMIT ${args.lastNRounds}
  `);

  const roundsAsc: RoundRow[] = (tail.rows as Array<{
    round_id: number;
    round_no: number;
    period_start: string;
    period_end: string;
    min_bid_price: number | null;
    regular_winning_bid: number | null;
    empty_slots: number | null;
    bid_status: string | null;
  }>)
    .slice()
    .reverse()
    .map((r) => ({
      roundId: r.round_id,
      roundNo: r.round_no,
      periodStart: r.period_start,
      periodEnd: r.period_end,
      minBidPrice: r.min_bid_price,
      regularWinningBid: r.regular_winning_bid,
      emptySlots: r.empty_slots,
      bidStatus: r.bid_status,
      ratio:
        r.regular_winning_bid != null && r.min_bid_price
          ? r.regular_winning_bid / r.min_bid_price
          : null,
    }));

  const latest = roundsAsc[roundsAsc.length - 1];
  return {
    keywordGroupId: h.keyword_group_id,
    keywordGroupName: h.keyword_group_name,
    product: h.product,
    categoryLvl1: h.category_lvl1,
    categoryLvl2: h.category_lvl2,
    latestWinning: latest?.regularWinningBid ?? null,
    latestEmptySlots: latest?.emptySlots ?? null,
    rounds: roundsAsc,
  };
}

export function computeInsights(summary: KeywordGroupSummary): Insights {
  const ratios = summary.rounds
    .map((r) => r.ratio)
    .filter((r): r is number => r != null);
  const vacancies = summary.rounds.filter((r) => (r.emptySlots ?? 0) > 0).length;
  const latestMin =
    summary.rounds[summary.rounds.length - 1]?.minBidPrice ?? null;

  if (ratios.length === 0) {
    return {
      meanRatio: null,
      vacancyRate:
        summary.rounds.length === 0 ? null : vacancies / summary.rounds.length,
      recommendedLow: null,
      recommendedHigh: null,
    };
  }

  const sorted = [...ratios].sort((a, b) => a - b);
  const p20 = sorted[Math.floor(sorted.length * 0.2)] ?? sorted[0];
  const p80 = sorted[Math.floor(sorted.length * 0.8)] ?? sorted[sorted.length - 1];
  const mean = ratios.reduce((a, b) => a + b, 0) / ratios.length;

  return {
    meanRatio: mean,
    vacancyRate: vacancies / summary.rounds.length,
    recommendedLow: latestMin ? Math.round(latestMin * p20 / 1000) * 1000 : null,
    recommendedHigh: latestMin ? Math.round(latestMin * p80 / 1000) * 1000 : null,
  };
}
```

- [ ] **Step 4: Type-check**

```
cd apps/dashboard
pnpm exec tsc --noEmit
cd ../..
```

Expected: no errors.

- [ ] **Step 5: Commit**

```
git add apps/dashboard/lib apps/dashboard/types
git commit -m "feat(dashboard): typed DB query layer for Screen 1"
```

---

## Task 7: Filter bar (cascading server-driven dropdowns via search params)

**Files:**
- Create: `apps/dashboard/components/bid-decision/filter-bar.tsx`

This component is a **server component**. Selections live in URL `searchParams`. Each `<form>` submits a GET, re-rendering the page with new params.

- [ ] **Step 1: Write `apps/dashboard/components/bid-decision/filter-bar.tsx`**

```tsx
import {
  getCategoriesLvl1,
  getCategoriesLvl2,
  getKeywordGroups,
  getProducts,
} from "@/lib/db/queries";
import type { ProductCode } from "@/types/bid-decision";

type FilterBarParams = {
  product: ProductCode;
  categoryLvl1: string | null;
  categoryLvl2: string | null;
  keywordGroupId: number | null;
  lastNRounds: number;
};

const RANGE_OPTIONS = [6, 12, 24, 52];

export async function FilterBar(props: FilterBarParams) {
  const [allProducts, lvl1, lvl2, kgs] = await Promise.all([
    getProducts(),
    getCategoriesLvl1(),
    props.categoryLvl1 ? getCategoriesLvl2(props.categoryLvl1) : Promise.resolve([]),
    props.categoryLvl1
      ? getKeywordGroups({
          product: props.product,
          categoryLvl1: props.categoryLvl1,
          categoryLvl2: props.categoryLvl2,
        })
      : Promise.resolve([]),
  ]);

  return (
    <form
      method="GET"
      action="/"
      className="flex flex-wrap items-end gap-2 border-b bg-background/95 px-6 py-3 text-sm"
    >
      <Field label="제품">
        <select name="product" defaultValue={props.product} className={selectCls}>
          {allProducts.map((p) => (
            <option key={p.code} value={p.code}>
              {p.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="대분류">
        <select
          name="cat1"
          defaultValue={props.categoryLvl1 ?? ""}
          className={selectCls}
        >
          <option value="">(전체)</option>
          {lvl1.map((c) => (
            <option key={c.id} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="소분류">
        <select
          name="cat2"
          defaultValue={props.categoryLvl2 ?? ""}
          className={selectCls}
          disabled={!props.categoryLvl1}
        >
          <option value="">(전체)</option>
          {lvl2.map((c) => (
            <option key={c.id} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="키워드그룹">
        <select
          name="kg"
          defaultValue={props.keywordGroupId?.toString() ?? ""}
          className={`${selectCls} min-w-[14rem]`}
          disabled={!props.categoryLvl1}
        >
          <option value="">(선택)</option>
          {kgs.map((kg) => (
            <option key={kg.id} value={kg.id}>
              {kg.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="기간">
        <select
          name="last"
          defaultValue={String(props.lastNRounds)}
          className={selectCls}
        >
          {RANGE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              최근 {n}회차
            </option>
          ))}
        </select>
      </Field>

      <button
        type="submit"
        className="ml-auto rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        적용
      </button>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

const selectCls =
  "rounded-md border border-input bg-background px-2 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring";
```

- [ ] **Step 2: Commit (the component is unused until Task 10 wires it in)**

```
git add apps/dashboard/components/bid-decision/filter-bar.tsx
git commit -m "feat(dashboard): cascading filter bar component"
```

---

## Task 8: Summary card

**Files:**
- Create: `apps/dashboard/components/bid-decision/summary-card.tsx`

- [ ] **Step 1: Write the card**

```tsx
import { Card, CardContent } from "@/components/ui/card";
import type { KeywordGroupSummary } from "@/types/bid-decision";
import { formatKRW } from "@/lib/format";

export function SummaryCard({ summary }: { summary: KeywordGroupSummary }) {
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-6 p-4">
        <div>
          <div className="text-xs text-muted-foreground">키워드그룹</div>
          <div className="text-lg font-semibold">
            {summary.keywordGroupName}
            <span className="ml-2 text-xs text-muted-foreground">
              {summary.product === "SEARCHING_VIEW" ? "서칭뷰" : "신제품검색"}
            </span>
          </div>
          <div className="text-xs text-muted-foreground">
            {summary.categoryLvl1} · {summary.categoryLvl2}
          </div>
        </div>

        <Stat label="최근 낙찰가" value={formatKRW(summary.latestWinning)} />
        <Stat
          label="공실 구좌"
          value={summary.latestEmptySlots == null ? "-" : `${summary.latestEmptySlots}구좌`}
          accent={(summary.latestEmptySlots ?? 0) > 0 ? "warn" : undefined}
        />
        <Stat
          label="현재 집행 브랜드"
          value="- (W4 예정)"
          muted
        />
      </CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
  accent,
  muted,
}: {
  label: string;
  value: string;
  accent?: "warn";
  muted?: boolean;
}) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={`text-lg font-semibold ${
          accent === "warn" ? "text-amber-600" : muted ? "text-muted-foreground" : ""
        }`}
      >
        {value}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```
git add apps/dashboard/components/bid-decision/summary-card.tsx
git commit -m "feat(dashboard): summary card for Screen 1"
```

---

## Task 9: Trend chart (Recharts)

**Files:**
- Create: `apps/dashboard/components/bid-decision/trend-chart.tsx`

- [ ] **Step 1: Write the chart**

```tsx
"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RoundRow } from "@/types/bid-decision";

export function TrendChart({ rounds }: { rounds: RoundRow[] }) {
  const data = rounds.map((r) => ({
    round: String(r.roundNo),
    minBid: r.minBidPrice,
    winning: r.regularWinningBid,
  }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis dataKey="round" className="text-xs" />
          <YAxis
            className="text-xs"
            tickFormatter={(v) =>
              v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : `${Math.round(v / 1000)}k`
            }
          />
          <Tooltip
            formatter={(value: number, name) => [
              value == null ? "-" : `${value.toLocaleString()}원`,
              name === "minBid" ? "최저입찰가" : "낙찰가",
            ]}
          />
          <Line
            type="monotone"
            dataKey="minBid"
            name="최저입찰가"
            stroke="#94a3b8"
            strokeWidth={1.5}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="winning"
            name="낙찰가"
            stroke="#0ea5e9"
            strokeWidth={2}
            dot={{ r: 3 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```
git add apps/dashboard/components/bid-decision/trend-chart.tsx
git commit -m "feat(dashboard): Recharts trend chart for Screen 1"
```

---

## Task 10: Round table

**Files:**
- Create: `apps/dashboard/components/bid-decision/round-table.tsx`

- [ ] **Step 1: Write the table**

```tsx
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { RoundRow } from "@/types/bid-decision";
import { formatDate, formatKRW, formatRatio } from "@/lib/format";

export function RoundTable({ rounds }: { rounds: RoundRow[] }) {
  // Show newest first in the table
  const display = [...rounds].reverse();
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-24">회차</TableHead>
            <TableHead className="w-40">집행기간</TableHead>
            <TableHead className="text-right">최저</TableHead>
            <TableHead className="text-right">낙찰</TableHead>
            <TableHead className="text-right">배수</TableHead>
            <TableHead className="text-right w-20">공실</TableHead>
            <TableHead className="w-40">집행 브랜드</TableHead>
            <TableHead className="w-32">상태</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {display.map((r) => (
            <TableRow key={r.roundId}>
              <TableCell className="font-mono text-xs">{r.roundNo}</TableCell>
              <TableCell className="text-xs">
                {formatDate(r.periodStart)}~{formatDate(r.periodEnd)}
              </TableCell>
              <TableCell className="text-right">{formatKRW(r.minBidPrice)}</TableCell>
              <TableCell className="text-right">{formatKRW(r.regularWinningBid)}</TableCell>
              <TableCell className="text-right">{formatRatio(r.ratio)}</TableCell>
              <TableCell className="text-right">
                {r.emptySlots == null ? "-" : `${r.emptySlots}구좌`}
              </TableCell>
              <TableCell className="text-muted-foreground text-xs">- (W4)</TableCell>
              <TableCell className="text-xs">{r.bidStatus ?? "-"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```
git add apps/dashboard/components/bid-decision/round-table.tsx
git commit -m "feat(dashboard): round-by-round table for Screen 1"
```

---

## Task 11: Insights card

**Files:**
- Create: `apps/dashboard/components/bid-decision/insights-card.tsx`

- [ ] **Step 1: Write the insights card**

```tsx
import { Card, CardContent } from "@/components/ui/card";
import type { Insights } from "@/types/bid-decision";
import { formatKRW, formatRatio } from "@/lib/format";

export function InsightsCard({ insights }: { insights: Insights }) {
  const vacancyPct =
    insights.vacancyRate == null
      ? "-"
      : `${Math.round(insights.vacancyRate * 100)}%`;

  return (
    <Card>
      <CardContent className="grid grid-cols-1 gap-4 p-4 md:grid-cols-3">
        <Stat
          label="평균 낙찰/최저 배수"
          value={formatRatio(insights.meanRatio)}
        />
        <Stat label="공실 발생률" value={vacancyPct} />
        <Stat
          label="추천 입찰가 레인지"
          value={
            insights.recommendedLow && insights.recommendedHigh
              ? `${formatKRW(insights.recommendedLow)} ~ ${formatKRW(
                  insights.recommendedHigh
                )}`
              : "-"
          }
        />
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```
git add apps/dashboard/components/bid-decision/insights-card.tsx
git commit -m "feat(dashboard): insights card for Screen 1"
```

---

## Task 12: Wire Screen 1 in `app/page.tsx`

**Files:**
- Replace: `apps/dashboard/app/page.tsx`

- [ ] **Step 1: Replace the placeholder page**

```tsx
import { FilterBar } from "@/components/bid-decision/filter-bar";
import { InsightsCard } from "@/components/bid-decision/insights-card";
import { RoundTable } from "@/components/bid-decision/round-table";
import { SummaryCard } from "@/components/bid-decision/summary-card";
import { TrendChart } from "@/components/bid-decision/trend-chart";
import {
  computeInsights,
  getKeywordGroupSummary,
} from "@/lib/db/queries";
import type { ProductCode } from "@/types/bid-decision";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function pickStr(v: string | string[] | undefined): string | null {
  if (Array.isArray(v)) return v[0] ?? null;
  return v ?? null;
}
function pickInt(v: string | string[] | undefined, fallback: number): number {
  const s = pickStr(v);
  const n = s ? Number(s) : NaN;
  return Number.isFinite(n) ? n : fallback;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;

  const product = (pickStr(sp.product) as ProductCode | null) ?? "SEARCHING_VIEW";
  const cat1 = pickStr(sp.cat1);
  const cat2 = pickStr(sp.cat2);
  const kgIdStr = pickStr(sp.kg);
  const keywordGroupId = kgIdStr ? Number(kgIdStr) : null;
  const lastNRounds = pickInt(sp.last, 12);

  const summary = keywordGroupId
    ? await getKeywordGroupSummary({ keywordGroupId, lastNRounds })
    : null;

  return (
    <div>
      <header className="border-b px-6 py-3">
        <h1 className="text-lg font-semibold">입찰 의사결정</h1>
        <p className="text-xs text-muted-foreground">
          키워드그룹별 회차 추이로 다음 입찰가를 결정합니다.
        </p>
      </header>

      <FilterBar
        product={product}
        categoryLvl1={cat1}
        categoryLvl2={cat2}
        keywordGroupId={keywordGroupId}
        lastNRounds={lastNRounds}
      />

      <div className="space-y-4 px-6 py-4">
        {!summary ? (
          <div className="rounded-md border border-dashed bg-muted/30 p-12 text-center text-sm text-muted-foreground">
            좌측 필터에서 키워드그룹을 선택하세요.
          </div>
        ) : (
          <>
            <SummaryCard summary={summary} />
            <TrendChart rounds={summary.rounds} />
            <InsightsCard insights={computeInsights(summary)} />
            <RoundTable rounds={summary.rounds} />
          </>
        )}
      </div>
    </div>
  );
}
```

⚠ **Next.js 16 note:** `searchParams` is a Promise in Next 15+. The signature above (`Promise<Record<...>>`) handles that. If your installed Next is actually 14, change to a plain object and remove the `await`. Check with `cat apps/dashboard/package.json | grep '"next"'`.

- [ ] **Step 2: Type-check + build**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
pnpm --filter dashboard exec tsc --noEmit
pnpm --filter dashboard build
```

Expected: both succeed.

- [ ] **Step 3: Commit**

```
git add apps/dashboard/app/page.tsx
git commit -m "feat(dashboard): wire Screen 1 (bid decision) at /"
```

---

## Task 13: Manual smoke + screenshot

**Files:** (none — runtime verification)

- [ ] **Step 1: Start dev server**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
pnpm --filter dashboard dev
```

Wait for `Ready in X.Xs`. Open http://localhost:3000.

- [ ] **Step 2: Exercise the filter chain**

1. Default screen shows the empty-state placeholder ("좌측 필터에서 키워드그룹을 선택하세요").
2. 제품 = 서칭뷰, 대분류 = 금융 → 소분류 dropdown populates.
3. 소분류 = 금융상품 → 키워드그룹 dropdown populates.
4. 키워드그룹 = 실비보험 (or any) → click 적용. Page reloads with URL `?product=SEARCHING_VIEW&cat1=금융&cat2=금융상품&kg=<id>&last=12`.
5. Summary card, chart, insights, table all render with real data.

- [ ] **Step 3: Capture a screenshot**

Use browser-harness (per the global CLAUDE.md) or any screenshot tool. Save as `docs/superpowers/screenshots/w2-screen1.png`.

Example via browser-harness:

```
browser-harness <<'PY'
new_tab("http://localhost:3000/?product=SEARCHING_VIEW&cat1=금융&cat2=금융상품&last=12")
wait_for_load()
capture_screenshot('C:/Users/MADUP/Documents/SearchingviewNewProduct/docs/superpowers/screenshots/w2-screen1-empty.png', max_dim=1600)
PY
```

Then again with a kg selected — find the id from the dropdown (or via SQL):

```
cd worker
uv run python -c "
import psycopg
from worker.config import load_settings
s = load_settings()
with psycopg.connect(s.database_url) as conn:
    cur = conn.cursor()
    cur.execute(\"\"\"
        SELECT kg.id FROM keyword_groups kg
        JOIN products p ON p.id = kg.product_id
        WHERE p.code = 'SEARCHING_VIEW' AND kg.name = '실비보험'
        LIMIT 1
    \"\"\")
    print(cur.fetchone())
"
```

Then:

```
browser-harness <<'PY'
new_tab("http://localhost:3000/?product=SEARCHING_VIEW&cat1=금융&cat2=금융상품&kg=<ID>&last=12")
wait_for_load()
capture_screenshot('C:/Users/MADUP/Documents/SearchingviewNewProduct/docs/superpowers/screenshots/w2-screen1-loaded.png', max_dim=1600)
PY
```

Stop the dev server (Ctrl+C).

- [ ] **Step 4: Append to README**

In `README.md`, under the W2 backfill section, add:

```markdown

### W2 Screen 1 ready

Decision screen live at `pnpm --filter dashboard dev` → http://localhost:3000.
Filters: 제품 / 대분류 / 소분류 / 키워드그룹 / 기간.
Screenshots in `docs/superpowers/screenshots/w2-screen1-*.png`.
```

- [ ] **Step 5: Commit + tag**

```
cd "C:/Users/MADUP/Documents/SearchingviewNewProduct"
git add README.md docs/superpowers/screenshots
git commit -m "docs: log W2 Screen 1 smoke + screenshots"
git tag w2-complete
```

---

## W2 Acceptance Criteria

- [ ] `worker/tests` has 19+ passing tests (15 from W1 + 4 backfill)
- [ ] `--backfill <dir>` ingests user's 70+ historical CSVs end-to-end with 0 errors
- [ ] `rounds` table has >= 20 distinct rounds; `round_keyword_groups` has thousands of rows
- [ ] `pnpm --filter dashboard build` succeeds with no type errors
- [ ] `http://localhost:3000/?product=SEARCHING_VIEW&cat1=금융&cat2=금융상품&kg=<id>` renders summary card, trend chart, insights, and round table
- [ ] Filter cascade works: changing 대분류 resets 소분류; changing 소분류 narrows 키워드그룹 list
- [ ] Two screenshots committed under `docs/superpowers/screenshots/`
- [ ] `git tag w2-complete` exists

---

## Self-Review Notes

**Spec coverage:**
- §5.1 Screen 1 — Tasks 6–12 (summary, chart, table, insights). Brand column is a deliberate placeholder ("- (W4)") to be filled in W4 — noted on screen and in spec §5.5.
- §9 Backfill — Tasks 1–3
- §10 W2 milestone — entire plan

**Deferred to W3+:**
- Job 1 (NOSP auto-download) → W3
- Job 3 (brand scrape) → W4 — Screen 1's "집행 브랜드" column shows `- (W4)` placeholder
- 경쟁사 등장 패턴 insight (depends on brand data) → W4 follow-up
- Screen 2/3/4, Sheets sync, Cloudflare deploy → W3–W5

**Type consistency check:**
- `KeywordGroupSummary.rounds` is ascending-by-roundNo. `TrendChart` consumes it directly (ascending = left-to-right time). `RoundTable` reverses internally for newest-first display. Both correct.
- `RoundRow.ratio` is computed once in the query layer and reused in table + insights — no double-computation drift.
- `formatKRW` is shared between `SummaryCard`, `RoundTable`, `InsightsCard`.

**Placeholder scan:** none. Every step has concrete code or commands.

**Known risks documented inline:**
- Next 16 `searchParams` Promise behavior (Task 12 step 1 footnote)
- shadcn CLI may not auto-detect Next 16 (Task 4 step 2 footnote)
- Backfill stall investigation guidance (Task 3 step 3 footnote)
