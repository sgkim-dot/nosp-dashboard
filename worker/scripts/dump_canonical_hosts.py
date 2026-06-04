"""Emit the keys of HOST_TO_BRAND as a JSON array for the dashboard.

The dashboard's brand-cleanup heuristic uses this set to skip
"first-word match" suspicion checks on hosts that are already
canonically mapped — eliminating false positives like 아이배냇.

Re-run this whenever HOST_TO_BRAND changes:
    uv run python scripts/dump_canonical_hosts.py
"""
import json
from pathlib import Path

from worker.lib.canonical_brand import HOST_TO_BRAND

OUT = (
    Path(__file__).resolve().parent.parent.parent
    / "apps"
    / "dashboard"
    / "lib"
    / "canonical-hosts.json"
)

hosts = sorted(HOST_TO_BRAND.keys())
OUT.write_text(json.dumps(hosts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {len(hosts)} canonical hosts to {OUT}")
