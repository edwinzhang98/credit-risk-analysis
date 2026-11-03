"""Click through every dashboard page, tab and radio option in headless Chromium and fail on any Streamlit exception.

Usage:  .venv/bin/python scripts/qa_dashboard.py      (prints one line per page; exit code 1 if anything failed)
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from screenshot_dashboard import PAGES, free_port, wait_for  # noqa: E402


def settle(page) -> None:
    page.wait_for_timeout(600)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60_000)
    page.wait_for_timeout(400)


def exceptions(page) -> list[str]:
    return [e.inner_text()[:300] for e in page.query_selector_all('[data-testid="stException"]')]


def main() -> int:
    from playwright.sync_api import sync_playwright

    port = free_port()
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "dashboard" / "app.py"), "--server.port", str(port), "--server.headless", "true"],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base, failures = f"http://127.0.0.1:{port}", 0
    try:
        wait_for(base)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1400})
            for i, (slug, title) in enumerate(PAGES, start=1):
                t0 = time.time()
                page.goto(f"{base}/{slug}" if i > 1 else base, wait_until="networkidle")
                page.wait_for_selector("h1", timeout=60_000)
                settle(page)
                first_render = time.time() - t0
                problems, checks = exceptions(page), 1
                charts = len(page.query_selector_all(".js-plotly-plot"))
                for tab in page.query_selector_all('[role="tab"]'):
                    tab.click()
                    settle(page)
                    checks += 1
                    problems += exceptions(page)
                    charts = max(charts, len(page.query_selector_all(".js-plotly-plot")))
                    # every radio option inside the visible tab panel / page
                    for radio in page.query_selector_all('[data-testid="stRadio"] label'):
                        if radio.is_visible():
                            radio.click()
                            settle(page)
                            checks += 1
                            problems += exceptions(page)
                if not page.query_selector_all('[role="tab"]'):
                    for radio in page.query_selector_all('[data-testid="stRadio"] label'):
                        if radio.is_visible():
                            radio.click()
                            settle(page)
                            checks += 1
                            problems += exceptions(page)
                status = "OK  " if not problems else "FAIL"
                failures += bool(problems)
                print(f"{status} {title:32s} first render {first_render:4.1f}s · {checks:2d} states checked · charts seen {charts}")
                for pr in problems[:3]:
                    print("      ", pr.replace("\n", " ")[:250])
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
