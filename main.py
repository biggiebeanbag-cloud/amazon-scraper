from fastapi import FastAPI
from playwright.sync_api import sync_playwright, TimeoutError
import random

app = FastAPI()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/127 Safari/537.36"

# 🔥 YOUR CORE EXTRACTION (SIMPLIFIED + STRONG)
JS_EXTRACTOR = """
() => {

let rating = "0";
let reviews = "0";

// PRIMARY (best)
const r = document.querySelector("#acrPopover");
if (r) {
  const t = r.getAttribute("title") || "";
  const m = t.match(/[\\d.]+/);
  if (m) rating = m[0];
}

// FALLBACK
if (rating === "0") {
  const alt = document.querySelector("span.a-icon-alt");
  if (alt) {
    const m = alt.innerText.match(/[\\d.]+/);
    if (m) rating = m[0];
  }
}

// REVIEWS
const rev = document.querySelector("#acrCustomerReviewText");
if (rev) {
  const m = rev.innerText.replace(/,/g,"").match(/\\d+/);
  if (m) reviews = m[0];
}

return {
  rating: rating,
  reviews: reviews
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
