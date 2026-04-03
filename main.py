from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio
import random
from playwright.async_api import async_playwright

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

async def scrape_asin(browser, asin: str):
    context = None
    try:
        # Better mimicking of a real browser
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        # Go to Amazon India
        url = f"https://www.amazon.in/dp/{asin}"
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Give it a moment to load the "hidden" rating elements
        await asyncio.sleep(5) 
        
        result = await page.evaluate("""() => {
            const grab = (sel) => document.querySelector(sel)?.innerText || "";
            
            // Try standard selectors first
            let rText = grab('#acrPopover') || grab('span[data-hook="rating-out-of-text"]');
            let vText = grab('#acrCustomerReviewText') || grab('[data-hook="total-review-count"]');

            // FAILSAFE: If the above are empty, look for any text matching the pattern
            if (!rText) {
                const bodyText = document.body.innerText;
                const match = bodyText.match(/([0-5]\\.[0-9]) out of 5 stars/);
                rText = match ? match[1] : "";
            }

            return { rText, vText };
        }""")

        await context.close()

        # Clean up the numbers
        rating = 0.0
        reviews = 0
        
        if result['rText']:
            r_match = str(result['rText']).match(r"([0-9]\.[0-9])")
            if r_match: rating = float(r_match.group(1))
            
        if result['vText']:
            v_match = str(result['vText']).replace(",", "").match(r"(\d+)")
            if v_match: reviews = int(v_match.group(1))

        return {"asin": asin, "rating": rating, "reviews": reviews}

    except Exception as e:
        if context: await context.close()
        return {"asin": asin, "rating": 0, "reviews": 0, "error": str(e)}

@app.get("/batch_amazon")
async def batch_amazon(asins: str):
    asin_list = [a.strip() for a in asins.split(",") if a.strip()]
    results = []
    
    async with async_playwright() as pw:
        # --no-sandbox is required for Render
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        for asin in asin_list:
            res = await scrape_asin(browser, asin)
            results.append(res)
        await browser.close()
    
    return JSONResponse(content=results)
