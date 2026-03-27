from fastapi import FastAPI
from playwright.sync_api import sync_playwright
import random

app = FastAPI()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119 Safari/537.36"
]

@app.get("/get_amazon")
def get_amazon(asin: str):

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800}
        )

        page = context.new_page()
        page.goto(f"https://www.amazon.in/dp/{asin}", timeout=60000)

        page.wait_for_timeout(2000)

        try:
            rating = page.locator("#acrPopover").get_attribute("title")
            reviews = page.locator("#acrCustomerReviewText").inner_text()

            rating = float(rating.split()[0])
            reviews = int(reviews.split()[0].replace(",", ""))

        except:
            rating = 0
            reviews = 0

        browser.close()

        return {
            "asin": asin,
            "rating": rating,
            "reviews": reviews
        }