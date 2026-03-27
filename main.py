from fastapi import FastAPI
from playwright.sync_api import sync_playwright, TimeoutError
import random

app = FastAPI()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/127 Safari/537.36"

# 🔥 YOUR CORE EXTRACTION (SIMPLIFIED + STRONG)
JS_EXTRACTOR = """
() => {

let rating = 0;
let reviews = 0;

// ✅ STRICT: ONLY MAIN PRODUCT RATING
const ratingNode = document.querySelector("#acrPopover");

if (ratingNode) {
  const text = ratingNode.getAttribute("title") || "";
  const match = text.match(/[\\d.]+/);
  if (match) rating = parseFloat(match[0]);
}

// ❌ DO NOT FALLBACK TO span.a-icon-alt (REMOVED)

// REVIEWS (safe)
const reviewNode = document.querySelector("#acrCustomerReviewText");

if (reviewNode) {
  const match = reviewNode.innerText.replace(/,/g,"").match(/\\d+/);
  if (match) reviews = parseInt(match[0]);
}

return {
  rating,
  reviews
};
}
"""


def scrape_one(context, asin):
    page = context.new_page()

    try:
        url = f"https://www.amazon.in/dp/{asin}?th=1&psc=1"

        page.goto(url, timeout=15000)

        # 🔥 SMART WAIT (not heavy)
        try:
            page.wait_for_selector("#acrPopover", timeout=5000)
        except:
            pass

        page.wait_for_timeout(1000)

        data = page.evaluate(JS_EXTRACTOR)

        rating = float(data.get("rating", 0))
        reviews = int(data.get("reviews", 0))

        page.close()

        return {
            "asin": asin,
            "rating": rating,
            "reviews": reviews
        }

    except TimeoutError:
        page.close()
        return {"asin": asin, "rating": 0, "reviews": 0}

    except Exception as e:
        page.close()
        return {"asin": asin, "rating": 0, "reviews": 0}


@app.get("/batch_amazon")
def batch_amazon(asins: str):

    asin_list = asins.split(",")

    # 🚨 SAFE LIMIT (Railway)
    asin_list = asin_list[:5]

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )

        context = browser.new_context(
            user_agent=USER_AGENT,
            locale="en-IN"
        )

        for asin in asin_list:

            data = scrape_one(context, asin)

            # 🔁 RETRY ON FAILURE
            if data["rating"] == 0:
                data = scrape_one(context, asin)

            results.append(data)

        browser.close()

    return results
