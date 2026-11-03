"""Capture every dashboard page to reports/figures/dashboard_<n>_<slug>.png for the README.

Starts `streamlit run dashboard/app.py` on a free port, waits for it, visits each page in headless Chromium,
and saves a full-page screenshot. Also records how long the first page takes to render.
Requires once:  .venv/bin/python -m playwright install chromium
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "figures"
PAGES = [
    ("overview", "Overview"),
    ("data_quality", "Data & Quality Audit"),
    ("portfolio", "Portfolio Snapshot"),
    ("model", "Model & Explainability"),
    ("threshold", "Cost-based Threshold Simulator"),
    ("swap_set", "Swap-set Analysis"),
    ("strategy", "Strategy & Monitoring Plan"),
]
PAGE_HEIGHT = {"threshold": 1620, "swap_set": 1350}  # pages whose main chart sits further down (Streamlit scrolls inside its own container)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(url: str, timeout: float = 60) -> None:
    import urllib.request

    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise TimeoutError(url)


def main() -> None:
    import argparse

    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser()
    ap.add_argument("--height", type=int, default=1100, help="viewport height in px (Streamlit scrolls inside the page, so this is the visible part)")
    ap.add_argument("--out", default=str(OUT), help="output folder")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "dashboard" / "app.py"), "--server.port", str(port), "--server.headless", "true"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        wait_for(base)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": args.height}, device_scale_factor=1.5)
            for i, (slug, title) in enumerate(PAGES, start=1):
                page.set_viewport_size({"width": 1440, "height": PAGE_HEIGHT.get(slug, args.height)})
                t0 = time.time()
                page.goto(f"{base}/{slug}" if i > 1 else base, wait_until="networkidle")
                page.wait_for_selector("h1", timeout=60_000)
                page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60_000)
                page.wait_for_timeout(2500)  # let Plotly finish drawing
                elapsed = time.time() - t0
                path = out / f"dashboard_{i}_{slug}.png"
                page.screenshot(path=str(path), full_page=True)
                print(f"{title:35s} rendered in {elapsed:5.1f}s -> {path}")
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    main()
