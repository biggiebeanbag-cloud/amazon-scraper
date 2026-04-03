from fastapi import FastAPI
import asyncio
import random
from playwright.async_api import async_playwright

app = FastAPI()

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
MAX_WORKERS = 4
MAX_RETRIES = 2
NAV_TIMEOUT = 30000

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
]

HEADERS = {
    "Accept-Language": "en-IN,en;q=0.9",
    "DNT": "1"
}

# --------------------------------------------------
# HEALTH
# --------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# --------------------------------------------------
# JS EXTRACTOR
# --------------------------------------------------
AMAZON_JS_EXTRACTOR = r"""
() => {

    let rating = null;
    let reviews = 0;

    // --------------------------------------------------
    // RATING
    // --------------------------------------------------

    const ratingSelectors = [
        '#acrPopover',
        'span[data-hook="rating-out-of-text"]',
        'i[data-hook="average-star-rating"] span',
        'span.a-icon-alt'
    ];

    for (const selector of ratingSelectors) {
        const nodes = document.querySelectorAll(selector);

        for (const node of nodes) {
            let text = '';

            if (node.getAttribute('title')) {
                text = node.getAttribute('title').trim();
            } else {
                text = node.innerText.trim();
            }

            const match = text.match(/([0-5](?:\.[0-9])?)\s*out\s*of\s*5/i);

            if (match) {
                rating = parseFloat(match[1]);
                break;
            }
        }

        if (rating !== null) break;
    }

    // --------------------------------------------------
    // REVIEWS
    // --------------------------------------------------

    const reviewSelectors = [
        '#acrCustomerReviewText',
        'span[data-hook="total-review-count"]'
    ];

    for (const selector of reviewSelectors) {
        const node = document.querySelector(selector);

        if (node) {
            const text = node.innerText.trim();
            const match = text.match(/([\d,]+)/);

            if (match) {
                reviews = parseInt(match[1].replace(/,/g, ''));
                break;
            }
        }
    }

    return {
        rating,
        reviews
    };
}
"""

# --------------------------------------------------
# SCRAPE SINGLE ASIN
# --------------------------------------------------
async def scrape_asin(browser, asin):

    url = f"https://www.amazon.in/dp/{asin}"

    for attempt in range(MAX_RETRIES + 1):
        page = None

        try:
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                locale="en-IN",
                extra_http_headers=HEADERS,
                viewport={"width": 1400, "height": 1000}
            )

            page = await context.new_page()

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=NAV_TIMEOUT
            )

            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(random.randint(1200, 2200))

            # Small scroll helps load review section
            await page.mouse.wheel(0, 1200)
            await page.wait_for_timeout(700)

            html = await page.content()
            lower_html = html.lower()

            if (
                "captcha" in lower_html or
                "robot check" in lower_html or
                "enter the characters you see below" in lower_html
            ):
                raise Exception("Amazon blocked request")

            data = await page.evaluate(AMAZON_JS_EXTRACTOR)

            rating = data.get("rating")
            reviews = data.get("reviews", 0)

            if rating is not None:
                await context.close()

                return {
                    "asin": asin,
                    "rating": rating,
                    "reviews": reviews
                }

            await context.close()

        except Exception:
            if page:
                try:
                    await page.close()
                except:
                    pass

        await asyncio.sleep(random.uniform(0.8, 1.5))

    return {
        "asin": asin,
        "rating": 0,
        "reviews": 0
    }

# --------------------------------------------------
# WORKER
# --------------------------------------------------
async def worker(browser, queue, results):

    while True:
        asin = await queue.get()

        if asin is None:
            queue.task_done()
            break

        result = await scrape_asin(browser, asin)
        results.append(result)

        queue.task_done()

# --------------------------------------------------
# BATCH ENDPOINT
# --------------------------------------------------
@app.get("/batch_amazon")
async def batch_amazon(asins: str):

    asin_list = [a.strip() for a in asins.split(",") if a.strip()]

    if not asin_list:
        return []

    queue = asyncio.Queue()
    results = []

    for asin in asin_list:
        await queue.put(asin)

    async with async_playwright() as pw:

        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )

        workers = [
            asyncio.create_task(worker(browser, queue, results))
            for _ in range(min(MAX_WORKERS, len(asin_list)))
        ]

        await queue.join()

        for _ in workers:
            await queue.put(None)

        await asyncio.gather(*workers)

        await browser.close()

    result_map = {item["asin"]: item for item in results}

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

    return ordered_results
