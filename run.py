"""One-command pipeline:  python run.py   (same as `make all`)

Stages (each can be run alone with --stage):
  sql        build the point-in-time feature tables in DuckDB (sql/0*.sql) and the data-quality tables (sql/dq/*.sql)
  notebooks  execute notebooks 01-04 in order (they produce models, predictions, metrics and dashboard caches)
  export     export executed notebooks to HTML in reports/
  report     build reports/report.html and the README / executive-summary figures

Raw data is read in place from `data_dir` in config.yaml (or the HC_DATA_DIR environment variable).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.config import load_config  # noqa: E402
from src.db import connect, run_sql_file  # noqa: E402

SQL_PIPELINE = [
    "sql/01_stg_base.sql",
    "sql/02_stg_static.sql",
    "sql/03_int_applprev_pit.sql",
    "sql/04_int_person_applicant.sql",
    "sql/05_fct_application_features.sql",
    "sql/06_abl_snapshot_as_provided.sql",
]
SQL_DQ = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "sql" / "dq").glob("dq_*.sql"))
NOTEBOOKS = ["01_data_audit", "02_feature_eng", "03_modeling", "04_threshold_and_strategy"]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def stage_sql(cfg: dict) -> None:
    con = connect(cfg)
    for f in SQL_PIPELINE + SQL_DQ:
        run_sql_file(con, f)
    con.close()


def _python_bin() -> str:
    return sys.executable


def stage_notebooks(cfg: dict) -> None:
    for nb in NOTEBOOKS:
        path = ROOT / "notebooks" / f"{nb}.ipynb"
        t0 = time.time()
        log(f"executing {path.relative_to(ROOT)}")
        subprocess.run(
            [_python_bin(), "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
             "--ExecutePreprocessor.timeout=3600", "--ExecutePreprocessor.kernel_name=python3", str(path)],
            check=True, cwd=ROOT / "notebooks",
        )
        log(f"done {nb} in {time.time() - t0:.0f}s")


def stage_export(cfg: dict) -> None:
    out = Path(cfg["reports_dir"])
    for nb in NOTEBOOKS:
        subprocess.run(
            [_python_bin(), "-m", "jupyter", "nbconvert", "--to", "html", "--output-dir", str(out), str(ROOT / "notebooks" / f"{nb}.ipynb")],
            check=True, cwd=ROOT,
        )
    log(f"exported {len(NOTEBOOKS)} notebooks to {out.relative_to(ROOT)}/")


def stage_report(cfg: dict) -> None:
    from src.report import build_report

    path = build_report(cfg)
    log(f"report written to {Path(path).relative_to(ROOT)}")


STAGES = {"sql": stage_sql, "notebooks": stage_notebooks, "export": stage_export, "report": stage_report}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", choices=list(STAGES), action="append", help="run only these stages (repeatable)")
    args = parser.parse_args()
    cfg = load_config()
    stages = args.stage or list(STAGES)
    t_all = time.time()
    log(f"raw data: {cfg['data_dir']}")
    for name in stages:
        t0 = time.time()
        log(f"== stage {name}")
        STAGES[name](cfg)
        log(f"== stage {name} finished in {time.time() - t0:.0f}s")
    log(f"pipeline finished in {(time.time() - t_all) / 60:.1f} min")


if __name__ == "__main__":
    main()
