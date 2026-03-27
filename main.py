from fastapi import FastAPI
from playwright.sync_api import sync_playwright
import random

app = FastAPI()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119 Safari/537.36"
]

def scrape_one(page, asin):
    try:
        page.goto(f"https://www.amazon.in/dp/{asin}", timeout=60000)
        page.wait_for_timeout(1500)

        rating = 0
        reviews = 0

        try:
            rating = float(page.locator("span.a-icon-alt").first.inner_text().split()[0])
        except:
            pass

        try:
            reviews = int(
                page.locator("#acrCustomerReviewText").inner_text().split()[0].replace(",", "")
            )
        except:
            pass

        return {
            "asin": asin,
            "rating": rating,
            "reviews": reviews
        }

    except:
        return {
            "asin": asin,
            "rating": 0,
            "reviews": 0
        }


@app.get("/batch_amazon")
def batch_amazon(asins: str):

    asin_list = asins.split(",")

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )

        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS)
        )

        page = context.new_page()

        for asin in asin_list:
            data = scrape_one(page, asin)

            # 🔁 RETRY IF FAILED
            if data["rating"] == 0:
                data = scrape_one(page, asin)

            results.append(data)

        browser.close()

    return results
