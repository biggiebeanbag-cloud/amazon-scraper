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

            result = await page.evaluate("""
() => {
    let rating = null;
    let reviews = 0;

    const ratingCandidates = [];

    const acrPopover = document.querySelector('#acrPopover');
    if (acrPopover) {
        ratingCandidates.push(acrPopover.getAttribute('title') || '');
    }

    const hookRating = document.querySelector("span[data-hook='rating-out-of-text']");
    if (hookRating) {
        ratingCandidates.push(hookRating.innerText || '');
    }

    const iconAlt = document.querySelector('.a-icon-alt');
    if (iconAlt) {
        ratingCandidates.push(iconAlt.innerText || '');
    }

    for (const text of ratingCandidates) {
        const match = text.match(/([0-5](?:\\.[0-9])?)\s*out\s*of\s*5/i);

        if (match) {
            const parsed = parseFloat(match[1]);

            if (!isNaN(parsed) && parsed > 0 && parsed <= 5) {
                rating = parsed;
                break;
            }
        }
    }

    const reviewCandidates = [];

    const reviewText = document.querySelector('#acrCustomerReviewText');
    if (reviewText) {
        reviewCandidates.push(reviewText.innerText || '');
    }

    const reviewHook = document.querySelector("span[data-hook='total-review-count']");
    if (reviewHook) {
        reviewCandidates.push(reviewHook.innerText || '');
    }

    for (const text of reviewCandidates) {
        const match = text.match(/[\\d,]+/);

        if (match) {
            const parsed = parseInt(match[0].replace(/,/g, ''));

            if (!isNaN(parsed)) {
                reviews = parsed;
                break;
            }
        }
    }

    return {
        rating: rating,
        reviews: reviews
    };
}
""")

            rating = result.get("rating")
            reviews = result.get("reviews", 0)

            if rating is None:
                rating = 0

            if reviews is None:
                reviews = 0

            try:
                await page.close()
            except:
                pass

            try:
                await context.close()
            except:
                pass

            return {
                "asin": asin,
                "rating": rating,
                "reviews": reviews
            }

        except Exception as e:
            print(f"ERROR for {asin} attempt {attempt}: {str(e)}")

            try:
                if page:
                    await page.close()
            except:
                pass

            try:
                if context:
                    await context.close()
            except:
                pass

            if attempt < MAX_RETRIES + 1:
                await asyncio.sleep(random.uniform(1, 2))

    return {
        "asin": asin,
        "rating": 0,
        "reviews": 0
    }

# ==================================================
# WORKER
# ==================================================
async def worker(browser, queue, results):

    while True:
        asin = await queue.get()

        if asin is None:
            queue.task_done()
            break

        try:
            result = await scrape_asin(browser, asin)
        except Exception as e:
            print(f"WORKER FAILURE for {asin}: {str(e)}")

            result = {
                "asin": asin,
                "rating": 0,
                "reviews": 0
            }

        results.append(result)
        queue.task_done()

# ==================================================
# BATCH ENDPOINT
# ==================================================
@app.get("/batch_amazon")
async def batch_amazon(asins: str):

    try:
        asin_list = [x.strip() for x in asins.split(",") if x.strip()]

        if not asin_list:
            return JSONResponse(content=[])

        queue = asyncio.Queue()
        results = []

        for asin in asin_list:
            await queue.put(asin)

        async with async_playwright() as pw:

            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--single-process"
                ]
            )

            workers = [
                asyncio.create_task(worker(browser, queue, results))
                for _ in range(min(MAX_CONCURRENT_PAGES, len(asin_list)))
            ]

            await queue.join()

            for _ in workers:
                await queue.put(None)

            await asyncio.gather(*workers)

            try:
                await browser.close()
            except:
                pass

        result_map = {
            item["asin"]: item
            for item in results
        }

        ordered_results = []

        for asin in asin_list:
            ordered_results.append(
                result_map.get(
                    asin,
                    {
                        "asin": asin,
                        "rating": 0,
                        "reviews": 0
                    }
                )
            )

        return JSONResponse(content=ordered_results)

    except Exception as e:
        print(f"BATCH ERROR: {str(e)}")

        fallback = []

        for asin in asins.split(","):
            asin = asin.strip()

            if asin:
                fallback.append({
                    "asin": asin,
                    "rating": 0,
                    "reviews": 0
                })

        return JSONResponse(content=fallback)
