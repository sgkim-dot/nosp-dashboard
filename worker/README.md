# Worker

Python 3.13 + uv. Owns CSV ingest, NOSP scraping, brand scraping, Sheets sync.

## Setup

1. Install uv: `pip install uv`
2. `cp .env.example .env.local` and fill in `DATABASE_URL` (Neon connection string).
3. `uv sync`

## JOB 2 — CSV ingest (W1)

Single file:

```bash
uv run python -m worker.jobs.csv_ingest --file path/to/file.csv --product SEARCHING_VIEW --kind bid_info
```

Or let the CLI auto-detect product + kind from the filename:

```bash
uv run python -m worker.jobs.csv_ingest --file "inbox/서칭뷰_회차별입찰정보.csv"
```

Watch mode (`inbox/` folder, manual-drop fallback):

```bash
uv run python -m worker.jobs.csv_ingest --watch
```

Filename auto-classification: any CSV starting with `서칭뷰_` or `신제품_` and containing either `회차별입찰정보` or `키워드그룹별최근낙찰가` is recognized.

Processed files are archived to `raw/YYYY-MM-DD/` and a row is written to `ingest_runs`.

## Tests

```bash
uv run pytest              # all tests
uv run pytest -m db        # only DB-touching tests (require .env.local)
uv run pytest -k parsers   # CSV parser tests only
```

`db_conn` fixture in `tests/conftest.py` opens a Neon transaction and rolls it back at teardown so tests do not pollute production data. Test fixtures use the synthetic keyword_group name `__테스트_실비보험__` to ensure isolation from real ingested data.
