"""Append one benchmark run row to results.jsonl, reading the fixture's own result.json.

Usage: python record.py ENGINE FAMILY SEED OUTDIR [KEY=VALUE ...]
Extra KEY=VALUE pairs carry engine-side metrics (steps_taken, seconds, host_rounds, cells, notes...).
Failed runs with a missing result.json are recorded as success=false, detail="no_result_json".
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent


def main() -> None:
    engine, family, seed, outdir = sys.argv[1], sys.argv[2], int(sys.argv[3]), Path(sys.argv[4])
    extra = {}
    for pair in sys.argv[5:]:
        key, _, value = pair.partition("=")
        extra[key] = value
    result_path = outdir / "result.json"
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine": engine,
        "family": family,
        "seed": seed,
        "partition": "development" if seed < 5 else ("regression" if seed < 8 else "holdout"),
    }
    if result_path.exists():
        raw = json.loads(result_path.read_text(encoding="utf-8"))
        row.update(
            success=bool(raw.get("success")),
            detail=raw.get("detail"),
            actions=raw.get("actions"),
            validation_errors=raw.get("validationErrors"),
            interaction_seconds=raw.get("interactionSeconds"),
            completed_utc=raw.get("completedUtc"),
        )
    else:
        row.update(success=False, detail="no_result_json", actions=None,
                   validation_errors=None, interaction_seconds=None, completed_utc=None)
    for key, value in extra.items():
        try:
            extra[key] = int(value)
        except ValueError:
            try:
                extra[key] = float(value)
            except ValueError:
                pass
        row[key] = extra[key]
    with (HERE / "results.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
