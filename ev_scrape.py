#!/usr/bin/env python3
"""Read the live "available/total" connector count (e.g. 2/2) from each Google Maps page.

Setup (once):
  pip install playwright
  playwright install chromium

Run:
  python3 ev_scrape.py            # one reading per charger, appended to ev_log.csv
  python3 ev_monitor.py summary   # same summary as the API version (reads ev_log.csv)

Schedule every 30 minutes, e.g. cron:
  */30 * * * * /usr/bin/python3 /path/to/ev_scrape.py

If a charger's count isn't found, a debug_<n>.png screenshot is saved so you can see
what the page looked like.
"""
import csv
import os
import re
import sys
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

CHARGERS = {
    "Zeon 1 (12.6426, 79.9389)": "https://maps.app.goo.gl/TDoSf3Nubrfhhyrh7",
    "Zeon 2 (12.4798, 79.8600)": "https://maps.app.goo.gl/ZDkyuL1EU6AM9Ppv9",
    "Zeon 3 (12.4467, 79.8381)": "https://maps.app.goo.gl/4KZJ5YX6v1u7LHau9",
}
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "ev_log.csv")
# A connector row looks like "CCS · 120 kW" followed by "2/2" (available/total).
ROW = re.compile(r"kW\s+(\d+)\s*/\s*(\d+)")


def read_counts(page, url, n):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:  # wait until a connector row shows up
        page.wait_for_function(
            "document.body.innerText.match(/kW\\s+\\d+\\s*\\/\\s*\\d+/)", timeout=20000
        )
    except Exception:
        pass
    rows = ROW.findall(page.inner_text("body"))
    if not rows:
        page.screenshot(path=os.path.join(HERE, f"debug_{n}.png"))
        return None
    available = sum(int(a) for a, _ in rows)
    total = sum(int(t) for _, t in rows)
    return total, available


def main():
    new = not os.path.exists(LOG)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(LOG, "a", newline="") as f, sync_playwright() as pw:
        w = csv.writer(f)
        if new:
            w.writerow(["time_utc", "charger", "total", "available", "out_of_service", "in_use", "google_updated"])
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(locale="en-IN", viewport={"width": 1280, "height": 900})
        for n, (name, url) in enumerate(CHARGERS.items(), 1):
            page = ctx.new_page()
            try:
                res = read_counts(page, url, n)
            except Exception as e:
                print(f"{name}: {e}", file=sys.stderr)
                res = None
            finally:
                page.close()
            if res is None:
                print(f"{name}: no connector count found", file=sys.stderr)
                w.writerow([now, name, "", "", "", "", ""])
            else:
                total, avail = res
                w.writerow([now, name, total, avail, "", total - avail, ""])
        browser.close()


if __name__ == "__main__":
    main()
