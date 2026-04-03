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
# Extract Rating + Reviews
# ---------------------------------------------------
def extract_data(html):
    soup = BeautifulSoup(html, "html.parser")

    rating = 0
    reviews = 0

    # Main Rating Selector
    rating_tag = soup.select_one("#acrPopover")
    if rating_tag:
        title = rating_tag.get("title", "")
        if "out of" in title:
            try:
                rating = float(title.split(" ")[0].replace(",", "."))
            except:
                pass

    # Fallback Rating Selector 1
    if rating == 0:
        rating_tag = soup.select_one("span[data-hook='rating-out-of-text']")
        if rating_tag:
            try:
                rating = float(rating_tag.text.split(" ")[0].replace(",", "."))
            except:
                pass

    # Fallback Rating Selector 2
    if rating == 0:
        possible_ratings = soup.select("span.a-size-base.a-color-base")
        for tag in possible_ratings:
            text = tag.text.strip().replace(",", ".")
            try:
                value = float(text)
                if 0 < value <= 5:
                    rating = value
                    break
            except:
                pass

    # Main Reviews Selector
    review_tag = soup.select_one("#acrCustomerReviewText")
    if review_tag:
        text = review_tag.text.strip()
        num = ''.join(filter(str.isdigit, text))
        if num:
            reviews = int(num)

    # Fallback Reviews Selector
    if reviews == 0:
        review_tag = soup.select_one("span[data-hook='total-review-count']")
        if review_tag:
            num = ''.join(filter(str.isdigit, review_tag.text))
            if num:
                reviews = int(num)

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

            if rating > 0:
                return {
                    "asin": asin,
                    "rating": rating,
                    "reviews": reviews
                }

        except Exception:
            pass

        time.sleep(random.uniform(0.5, 1.0))

    return {
        "asin": asin,
        "rating": 0,
        "reviews": 0
    }

# ---------------------------------------------------
# Batch Endpoint (Sequential One By One)
# ---------------------------------------------------
@app.get("/batch_amazon")
def batch_amazon(asins: str):

    asin_list = [a.strip() for a in asins.split(",") if a.strip()]
    results = []

    for asin in asin_list:
        try:
            result = fetch_amazon(asin)
            results.append(result)

            # Small pause between ASINs to reduce Amazon blocking
            time.sleep(random.uniform(0.3, 0.8))

        except Exception:
            results.append({
                "asin": asin,
                "rating": 0,
                "reviews": 0
            })

    return results
