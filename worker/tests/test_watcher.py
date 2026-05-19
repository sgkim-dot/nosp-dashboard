from pathlib import Path
from unittest.mock import MagicMock

from worker.watcher import _IngestHandler


def test_handler_dispatches_only_matching_csv_files(tmp_path: Path):
    ingest = MagicMock()
    handler = _IngestHandler(ingest_fn=ingest)

    good = tmp_path / "서칭뷰_회차별입찰정보.csv"
    good.write_text("dummy", encoding="utf-8")

    bad = tmp_path / "notes.txt"
    bad.write_text("dummy", encoding="utf-8")

    other = tmp_path / "random.csv"
    other.write_text("dummy", encoding="utf-8")

    handler._handle(str(good))
    handler._handle(str(bad))
    handler._handle(str(other))

    assert ingest.call_count == 1
    # First positional arg of the call should be the path that was passed to
    # ingest_fn — note that _handle archives before invoking, so the path
    # received by ingest_fn is the archived destination (under raw/<date>/).
    # We only assert that ingest was called exactly once. The archive path
    # behavior is implicit in the handler implementation.
