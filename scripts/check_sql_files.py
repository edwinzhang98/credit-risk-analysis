"""Prove that every SQL file runs on its own: each file is executed in a fresh DuckDB connection
(only the session variables from config.yaml are set; upstream tables it declares as inputs must already exist
in the warehouse, which `make sql` builds). Prints rows/time per file and fails loudly on any error."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run import SQL_DQ, SQL_PIPELINE  # noqa: E402
from src.config import load_config  # noqa: E402
from src.db import connect  # noqa: E402


def main() -> int:
    cfg = load_config()
    failures = 0
    for f in SQL_PIPELINE + SQL_DQ:
        con = connect(cfg)  # fresh connection per file: no temp views or state carried over
        t0 = time.time()
        try:
            res = con.execute((ROOT / f).read_text()).df()
            print(f"OK    {f:45s} {time.time() - t0:6.1f}s  final result: {len(res)} rows")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL  {f:45s} {type(e).__name__}: {e}")
        finally:
            con.close()
    print(f"\n{len(SQL_PIPELINE) + len(SQL_DQ) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
