"""Load `config.yaml` and resolve paths. Every script, notebook and the dashboard read settings from here."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: str | os.PathLike | None = None) -> dict:
    """Return the project config with absolute paths.

    The raw-data folder comes from `config.yaml` unless the environment variable HC_DATA_DIR is set.
    Output folders are created on first use.
    """
    path = Path(path) if path else ROOT / "config.yaml"
    with open(path) as f:
        cfg = yaml.safe_load(f)

    data_dir = os.environ.get("HC_DATA_DIR") or cfg["data_dir"]
    cfg["data_dir"] = str(Path(os.path.expanduser(data_dir)).resolve())
    for key in ("warehouse", "processed_dir", "artifacts_dir", "reports_dir"):
        cfg[key] = str((ROOT / cfg[key]).resolve())
    for key in ("processed_dir", "artifacts_dir", "reports_dir"):
        Path(cfg[key]).mkdir(parents=True, exist_ok=True)
    Path(cfg["warehouse"]).parent.mkdir(parents=True, exist_ok=True)
    return cfg


def processed(cfg: dict, name: str) -> Path:
    """Path of a file in the processed-data folder."""
    return Path(cfg["processed_dir"]) / name


def artifact(cfg: dict, name: str) -> Path:
    """Path of a file in the model-artifacts folder."""
    return Path(cfg["artifacts_dir"]) / name
