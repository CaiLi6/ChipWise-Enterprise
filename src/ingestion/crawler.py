"""Playwright-based datasheet crawler (§3C3)."""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

MANUFACTURER_CONFIGS: dict[str, dict[str, Any]] = {
    "ST": {
        "base_url": "https://www.st.com/en/microcontrollers-microprocessors.html",
        "search_pattern": "a[href*='datasheet']",
        "max_per_run": 50,
    },
    "TI": {
        "base_url": "https://www.ti.com/microcontrollers-mcus-processors/overview.html",
        "search_pattern": "a[href*='.pdf']",
        "max_per_run": 50,
    },
    "NXP": {
        "base_url": "https://www.nxp.com/products/processors-and-microcontrollers:MICROCONTROLLERS-AND-PROCESSORS",
        "search_pattern": "a[href*='document']",
        "max_per_run": 50,
    },
}


class DatasheetCrawler:
    """Crawl manufacturer websites for new datasheets."""

    def __init__(self, download_dir: str = "data/documents") -> None:
        self._download_dir = Path(download_dir)

    async def crawl(self, manufacturer: str) -> list[str]:
        """Crawl a manufacturer site and return downloaded PDF paths."""
        config = MANUFACTURER_CONFIGS.get(manufacturer)
        if not config:
            logger.warning("Unknown manufacturer: %s", manufacturer)
            return []

        try:
            from playwright.async_api import async_playwright  # type: ignore[import-not-found]
        except ImportError:
            logger.error("Playwright not installed")
            return []

        downloaded: list[str] = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=random.choice(USER_AGENTS)
                )
                page = await context.new_page()

                await page.goto(config["base_url"], timeout=30000)
                await page.wait_for_load_state("networkidle")

                # Find PDF links
                links = await page.query_selector_all(config["search_pattern"])
                pdf_urls: list[str] = []

                for link in links[:config["max_per_run"]]:
                    href = await link.get_attribute("href")
                    if href and href.endswith(".pdf"):
                        pdf_urls.append(href)

                # Download with rate limiting
                for url in pdf_urls[:config["max_per_run"]]:
                    try:
                        delay = random.uniform(2.0, 5.0)
                        await page.wait_for_timeout(int(delay * 1000))

                        dest_dir = self._download_dir / manufacturer
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        filename = url.split("/")[-1]
                        dest_path = dest_dir / filename

                        if dest_path.exists():
                            continue  # Skip already downloaded

                        response = await page.request.get(url)
                        if response.ok:
                            content = await response.body()
                            dest_path.write_bytes(content)
                            downloaded.append(str(dest_path))
                    except Exception:
                        logger.warning("Failed to download %s", url)

                await browser.close()

        except Exception:
            logger.exception("Crawl failed for %s", manufacturer)

        return downloaded

    async def crawl_all(self) -> dict[str, list[str]]:
        """Crawl all configured manufacturers."""
        results: dict[str, list[str]] = {}
        for mfr in MANUFACTURER_CONFIGS:
            results[mfr] = await self.crawl(mfr)
        return results
