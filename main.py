from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio
import random
import time
from playwright.async_api import async_playwright

app = FastAPI()

# ==================================================
# CONFIG - Optimized for Render Free Tier & Accuracy
# ==================================================
MAX_CONCURRENT_PAGES = 2  # 2 is the sweet spot for memory vs speed
MAX_RETRIES = 2
NAVIGATION_TIMEOUT = 45000  # Increased to 45s for slow Render networks
PAGE_WAIT_MS = 2500         # Time to wait after scroll

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": int(time.time())}

# ==================================================
# SCRAPE ENGINE: Hardened for Timing & Accuracy
# ==================================================
async def scrape_asin(browser, asin: str):
    url = f"https://www.amazon.in/dp/{asin}"
    
    for attempt in range(1, MAX_RETRIES + 2):
        context = None
        page = None
        try:
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1920, "height": 1080},
                extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"}
            )
            page = await context.new_page()
            
            # STEP 1: Wait for network to settle
            await page.goto(url, wait_until="networkidle", timeout=NAVIGATION_TIMEOUT)
            
            # STEP 2: Scroll to trigger "Lazy Load" of review data
            await page.mouse.wheel(0, 800)
            
            # STEP 3: Explicit wait for JS to render the numbers (CRITICAL)
            await asyncio.sleep(PAGE_WAIT_MS / 1000) 

            # Bot Check
            content = await page.content()
            if any(term in content.lower() for term in ["captcha", "robot check", "automated access"]):
                raise Exception("Amazon Anti-Bot Triggered")

            # STEP 4: Scoped Extraction (Ignore "Sponsored" items)
            result = await page.evaluate("""
            () => {
                let rating = 0;
                let reviews = 0;

                // Scope to the specific product block only
                const mainContainer = document.querySelector('#ppd') || 
                                     document.querySelector('#centerCol') || 
                                     document.querySelector('#dp-container') || 
                                     document.body;

                // Rating Logic
                const ratEl = mainContainer.querySelector('#acrPopover') || 
                             mainContainer.querySelector('span[data-hook="rating-out-of-text"]') ||
                             mainContainer.querySelector('.a-icon-star');
                
                if (ratEl) {
                    const text = ratEl.innerText || ratEl.getAttribute('title') || '';
                    const match = text.match(/([0-5](?:\\.[0-9])?)\s*out\s*of\s*5/i);
                    if (match) rating = parseFloat(match[1]);
                }

                // Review Logic
                const revEl = mainContainer.querySelector('#acrCustomerReviewText') || 
                             mainContainer.querySelector('span[data-hook="total-review-count"]');
                
                if (revEl) {
                    const text = revEl.innerText || '';
                    const match = text.replace(/,/g, '').match(/\\d+/);
                    if (match) reviews = parseInt(match[0], 10);
                }

                return { rating, reviews };
            }
            """)

            await context.close()
            return {"asin": asin, "rating": result["rating"], "reviews": result["reviews"]}

        except Exception as e:
            print(f"DEBUG: {asin} Attempt {attempt} failed: {str(e)}")
            if context: await context.close()
            if attempt < MAX_RETRIES + 1:
                await asyncio.sleep(random.uniform(3, 6))

    return {"asin": asin, "rating": 0, "reviews": 0}

# ==================================================
# BATCHING & WORKER QUEUE
# ==================================================
async def worker(browser, queue, results):
    while True:
        asin = await queue.get()
        if asin is None:
            queue.task_done()
            break
        try:
            res = await scrape_asin(browser, asin)
            results.append(res)
        finally:
            queue.task_done()

@app.get("/batch_amazon")
async def batch_amazon(asins: str):
    asin_list = [a.strip() for a in asins.split(",") if a.strip()]
    if not asin_list: return JSONResponse(content=[])

    results = []
    queue = asyncio.Queue()
    for a in asin_list: await queue.put(a)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        
        workers = [
            asyncio.create_task(worker(browser, queue, results))
            for _ in range(min(MAX_CONCURRENT_PAGES, len(asin_list)))
        ]

        await queue.join()
        for _ in workers: await queue.put(None)
        await asyncio.gather(*workers)
        await browser.close()

    res_map = {r["asin"]: r for r in results}
    return JSONResponse(content=[res_map.get(a, {"asin": a, "rating": 0, "reviews": 0}) for a in asin_list])
