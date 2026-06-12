from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright


def render_png_map(
    path: Path,
    job_id: str,
    bbox: dict,
    *,
    zoom: int | None = None,
    frontend_url: str | None = None,
    api_url: str | None = None,
    width: int = 1600,
    height: int = 1000,
    scale: int = 2,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frontend = (frontend_url or os.getenv("FRONTEND_RENDER_URL") or "http://nginx").rstrip("/")
    api = (api_url or os.getenv("API_RENDER_URL") or "http://api:8000").rstrip("/")
    query = urlencode({
        "job_id": job_id,
        "api": api,
        "min_lon": bbox["min_lon"],
        "min_lat": bbox["min_lat"],
        "max_lon": bbox["max_lon"],
        "max_lat": bbox["max_lat"],
    })
    if zoom is not None:
        query += f"&zoom={zoom}"
    url = f"{frontend}/render-preview.html?{query}"
    executable_path = os.getenv("CHROMIUM_PATH") or "/usr/bin/chromium"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=executable_path,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=scale,
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_function("window.__RENDER_READY__ === true", timeout=90_000)
        page.screenshot(path=str(path), full_page=False)
        browser.close()
