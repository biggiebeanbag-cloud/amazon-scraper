from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio
import random
import time
from playwright.async_api import async_playwright

app = FastAPI()

# ==================================================
# CONFIG
# ==================================================
MAX_CONCURRENT_PAGES = 3
MAX_RETRIES = 2
NAVIGATION_TIMEOUT = 25000
PAGE_WAIT_MS = 1200

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/126.0.0.0 Mobile Safari/537.36"
]

# ==================================================
# HEALTH
# ==================================================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": int(time.time())
    }

# ==================================================
# SCRAPE ONE ASIN
# ==================================================
async def scrape_asin(browser, asin: str):

    url = f"https://www.amazon.in/dp/{asin}"

    for attempt in range(1, MAX_RETRIES + 2):

        context = None
        page = None

        try:
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                locale="en-IN",
                viewport={"width": 1440, "height": 1400},
                extra_http_headers={
                    "Accept-Language": "en-IN,en;q=0.9",
                    "DNT": "1",
                    "Upgrade-Insecure-Requests": "1"
                }
            )

            page = await context.new_page()

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT
            )

            await page.wait_for_timeout(PAGE_WAIT_MS)

            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass

            await page.mouse.wheel(0, 1200)
            await page.wait_for_timeout(500)

            html = await page.content()
            lower_html = html.lower()

            if (
                "captcha" in lower_html or
                "robot check" in lower_html or
                "enter the characters you see below" in lower_html
            ):
                raise Exception("Amazon block detected")

            result = await page.evaluate(
                """
                () => {
                    let rating = null;
                    let reviews = 0;

                    const ratingCandidates = [];

                    const acrPopover = document.querySelector('#acrPopover');
        return JSONResponse(fallback)
