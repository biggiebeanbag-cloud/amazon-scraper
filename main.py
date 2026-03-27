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
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )

        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 800}
        )

        page = context.new_page()
        page.goto(f"https://www.amazon.in/dp/{asin}", timeout=60000)

        # 🔥 WAIT FOR PAGE TO LOAD PROPERLY
        try:
            page.wait_for_selector("#acrPopover", timeout=8000)
        except:
            pass

        page.wait_for_timeout(2000)

        rating = 0
        reviews = 0

        try:
            # PRIMARY METHOD
            rating_text = page.locator("#acrPopover").get_attribute("title")
            review_text = page.locator("#acrCustomerReviewText").inner_text()

            if rating_text:
                rating = float(rating_text.split()[0])

            if review_text:
                reviews = int(review_text.split()[0].replace(",", ""))

        except:
            pass

        # 🔥 FALLBACK METHOD (VERY IMPORTANT)
        if rating == 0:
            try:
                rating_alt = page.locator("span.a-icon-alt").first.inner_text()
                rating = float(rating_alt.split()[0])
            except:
                pass

        if reviews == 0:
            try:
                review_alt = page.locator("#acrCustomerReviewText").inner_text()
                reviews = int(review_alt.split()[0].replace(",", ""))
            except:
                pass

        browser.close()

        return {
            "asin": asin,
            "rating": rating,
            "reviews": reviews
        }
