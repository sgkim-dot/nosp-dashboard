from pathlib import Path
from unittest.mock import patch

from worker.backfill import backfill_directory, classify_and_sort

FIXTURES = Path(__file__).parent / "fixtures" / "backfill"


def test_classify_and_sort_groups_bid_info_before_winning(tmp_path: Path):
    for f in FIXTURES.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes())

    sorted_paths = classify_and_sort(tmp_path)
    kinds = [p.kind for p in sorted_paths]
    bi_indices = [i for i, k in enumerate(kinds) if k == "bid_info"]
    w_indices = [i for i, k in enumerate(kinds) if k == "winning"]
    assert max(bi_indices) < min(w_indices)


def test_classify_and_sort_numeric_filename_order(tmp_path: Path):
    for f in FIXTURES.iterdir():
        (tmp_path / f.name).write_bytes(f.read_bytes())

    sorted_paths = classify_and_sort(tmp_path)
    sv_bid = [
        p.path.name for p in sorted_paths if p.product == "SEARCHING_VIEW" and p.kind == "bid_info"
    ]
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
    assert calls[0][1] == "bid_info"
    assert calls[-1][1] == "winning"
