"""Launch one fresh GeneralFixture case and print its case.json.

Usage: python start_case.py ENGINE FAMILY SEED
Creates bench-jev/ENGINE/FAMILY-seedSEED/ (deleted first for a clean protocol), starts the fixture,
waits for case.json, prints {"outdir": ..., "case": {...}}.
"""

from __future__ import annotations

import ctypes
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
EXE = REPO / "GeneralFixture.exe"


def main() -> None:
    engine, family, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    outdir = HERE / engine / f"{family}-seed{seed}"
    if outdir.exists():
        shutil.rmtree(outdir)
    params = f'"{family}" {seed} "{outdir}"'
    result = ctypes.windll.shell32.ShellExecuteW(None, "open", str(EXE), params, str(REPO), 1)
    if result <= 32:
        print(json.dumps({"error": f"ShellExecuteW failed: {result}"}))
        sys.exit(1)
    case_path = outdir / "case.json"
    deadline = time.time() + 15
    while time.time() < deadline:
        if case_path.exists():
            break
        time.sleep(0.3)
    if not case_path.exists():
        print(json.dumps({"error": "case.json not written", "outdir": str(outdir)}))
        sys.exit(1)
    case = json.loads(case_path.read_text(encoding="utf-8"))
    print(json.dumps({"outdir": str(outdir), "case": case}, ensure_ascii=False))


if __name__ == "__main__":
    main()
