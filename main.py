from fastapi import FastAPI
import requests
import random
import time
from bs4 import BeautifulSoup

app = FastAPI()

# ---------------------------------------------------
# Health Endpoint
# ---------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# ---------------------------------------------------
# User Agents
# ---------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edg/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 Version/15.0 Mobile Safari/604.1"
]

ACCEPT_LANGUAGES = [
    "en-IN,en;q=0.9",
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9"
]

REFERERS = [
    "https://www.amazon.in/",
    "https://www.google.com/",
    "https://www.bing.com/"
]

# ---------------------------------------------------
# Shared Session
# ---------------------------------------------------
session = requests.Session()

# ---------------------------------------------------
# Block Detection
# ---------------------------------------------------
def is_blocked(html):
    text = html.lower()

    return (
        "captcha" in text or
        "robot check" in text or
        "enter the characters you see below" in text or
        "sorry, we just need to make sure you're not a robot" in text or
        len(html) < 3000
    )

# ---------------------------------------------------
# Extract Rating + Reviews Strictly
# ---------------------------------------------------
def extract_data(html):
    soup = BeautifulSoup(html, "html.parser")

    rating = None
    reviews = 0

    # ---------------------------------------------------
    # Main Rating Selector
    # ---------------------------------------------------
    rating_tag = soup.select_one("#acrPopover")

    if rating_tag:
        title = rating_tag.get("title", "").strip()

        if "out of" in title.lower():
            try:
                value = float(title.split(" ")[0].replace(",", "."))
                if 0 < value <= 5:
                    rating = value
            except:
                pass

    # ---------------------------------------------------
    # Fallback Rating Selector
    # ---------------------------------------------------
    if rating is None:
        rating_tag = soup.select_one("span[data-hook='rating-out-of-text']")

        if rating_tag:
            text = rating_tag.get_text(strip=True)

            if "out of" in text.lower():
                try:
                    value = float(text.split(" ")[0].replace(",", "."))
                    if 0 < value <= 5:
                        rating = value
                except:
                    pass

    # ---------------------------------------------------
    # Main Review Selector
    # ---------------------------------------------------
    review_tag = soup.select_one("#acrCustomerReviewText")

    if review_tag:
        text = review_tag.get_text(strip=True)
        digits = ''.join(filter(str.isdigit, text))

        if digits:
            reviews = int(digits)

    # ---------------------------------------------------
    # Fallback Review Selector
    # ---------------------------------------------------
    if reviews == 0:
        review_tag = soup.select_one("span[data-hook='total-review-count']")

        if review_tag:
            digits = ''.join(filter(str.isdigit, review_tag.get_text(strip=True)))

            if digits:
                reviews = int(digits)

    # ---------------------------------------------------
    # Important Rule:
    # If no reviews exist, rating should be treated as missing
    # ---------------------------------------------------
    if reviews == 0:
        rating = None

    return rating, reviews

# ---------------------------------------------------
# Fetch Single ASIN
# ---------------------------------------------------
def fetch_amazon(asin):
    url = f"https://www.amazon.in/dp/{asin}"

    for attempt in range(3):

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": random.choice(ACCEPT_LANGUAGES),
            "Referer": random.choice(REFERERS),
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }

        try:
            response = session.get(
                url,
                headers=headers,
                timeout=6
            )

            if response.status_code != 200:
                time.sleep(0.5)
                continue

            html = response.text

            if is_blocked(html):
                time.sleep(random.uniform(0.5, 1.0))
                continue

            rating, reviews = extract_data(html)

            # Only return real product review data
            if rating is not None and reviews > 0:
                return {
                    "asin": asin,
                    "rating": rating,
                    "reviews": reviews
                }

            # Product exists but no reviews / no rating
            return {
                "asin": asin,
                "rating": None,
                "reviews": 0
            }

        except Exception:
            pass

        time.sleep(random.uniform(0.5, 1.0))

    return {
        "asin": asin,
        "rating": None,
        "reviews": 0
    }

# ---------------------------------------------------
# Batch Endpoint
# ---------------------------------------------------
@app.get("/batch_amazon")
def batch_amazon(asins: str):

    asin_list = [a.strip() for a in asins.split(",") if a.strip()]
    results = []

    for asin in asin_list:
        try:
            result = fetch_amazon(asin)
            results.append(result)

            # Small pause to reduce blocking
            time.sleep(random.uniform(0.3, 0.8))

        except Exception:
            results.append({
                "asin": asin,
                "rating": None,
                "reviews": 0
            })

    return results
