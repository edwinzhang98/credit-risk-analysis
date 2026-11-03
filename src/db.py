"""DuckDB helpers: open the local warehouse with the session variables the SQL files expect, and run SQL files.

Run a single SQL file from the command line (each file in sql/ is self-contained apart from its declared inputs):

    python -m src.db sql/03_int_applprev_pit.sql
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import duckdb

from src.config import ROOT, load_config


def _quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def connect(cfg: dict | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the warehouse and set the variables used by sql/*.sql (`data_dir` and the split months)."""
    cfg = cfg or load_config()
    con = duckdb.connect(cfg["warehouse"], read_only=read_only)
    con.execute(f"SET threads = {int(cfg['duckdb']['threads'])}")
    con.execute(f"SET memory_limit = {_quote(cfg['duckdb']['memory_limit'])}")
    con.execute("SET preserve_insertion_order = false")
    con.execute("SET enable_progress_bar = false")
    con.execute(f"SET VARIABLE data_dir = {_quote(cfg['data_dir'])}")
    for split, (start, end) in cfg["split"].items():
        con.execute(f"SET VARIABLE {split}_start = {int(start)}")
        con.execute(f"SET VARIABLE {split}_end = {int(end)}")
    return con


def run_sql_file(con: duckdb.DuckDBPyConnection, path: str | Path, verbose: bool = True) -> float:
    """Execute every statement in a .sql file; returns elapsed seconds."""
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    sql = path.read_text()
    t0 = time.time()
    con.execute(sql)
    elapsed = time.time() - t0
    if verbose:
        print(f"[sql] {path.relative_to(ROOT)} ... {elapsed:.1f}s")
    return elapsed


def query(sql: str, cfg: dict | None = None):
    """Run a read-only query against the warehouse and return a pandas DataFrame."""
    con = connect(cfg, read_only=True)
    try:
        return con.execute(sql).df()
    finally:
        con.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python -m src.db sql/<file>.sql [more files...]")
    connection = connect()
    for file in sys.argv[1:]:
        run_sql_file(connection, file)
    connection.close()
