from fastapi import FastAPI
import requests
import random
import time
from bs4 import BeautifulSoup

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

# 🔥 FULL USER AGENTS
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edg/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 Version/15.0 Mobile Safari/604.1"
]

# 🔥 BLOCK DETECTION
def is_blocked(html):
    text = html.lower()
    return (
        "captcha" in text or
        "robot check" in text or
        "enter the characters you see below" in text or
        "sorry, we just need to make sure you're not a robot" in text or
        len(html) < 3000
    )

# 🔥 TITLE + PRICE CHECK
def extract_title_price(html):
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    price = ""

    # Title selectors
    title_selectors = [
        "#productTitle",
        "span#productTitle",
        "#title"
    ]

    for selector in title_selectors:
        tag = soup.select_one(selector)
        if tag:
            title = tag.get_text(strip=True)
            if title:
                break

    # Price selectors
    price_selectors = [
        ".a-price .a-offscreen",
        ".reinventPricePriceToPayMargin span.a-offscreen",
        "span.a-price-whole",
        ".a-price-whole"
    ]

    for selector in price_selectors:
        tag = soup.select_one(selector)
        if tag:
            price = tag.get_text(strip=True)
            if price:
                break

    return title, price

# 🔥 STRICT EXTRACTION
def extract_data(html):
    soup = BeautifulSoup(html, "html.parser")

    rating = 0
    reviews = 0

    # Original rating logic only
    rating_tag = soup.select_one("#acrPopover")
    if rating_tag:
        title = rating_tag.get("title", "")
        if "out of" in title:
            try:
                rating = float(title.split(" ")[0])
            except:
                pass

    # Original review logic only
    review_tag = soup.select_one("#acrCustomerReviewText")
    if review_tag:
        text = review_tag.text.strip()
        num = ''.join(filter(str.isdigit, text))
        if num:
            reviews = int(num)

    return rating, reviews

# 🔥 MAIN FETCH LOGIC (5 ATTEMPTS, MAX 15 SECONDS)
def fetch_amazon(asin):
    url = f"https://www.amazon.in/dp/{asin}"

    start_time = time.time()

    last_title = ""
    last_price = ""

    for attempt in range(5):

        # Stop after 15 seconds total
        elapsed = time.time() - start_time
        if elapsed >= 15:
            break

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": random.choice([
                "en-IN,en;q=0.9",
                "en-US,en;q=0.9",
                "en-GB,en;q=0.9"
            ]),
            "Referer": random.choice([
                "https://www.amazon.in/",
                "https://www.google.com/",
                "https://www.bing.com/"
            ]),
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=8
            )

            html = response.text

            # 🚨 BLOCK CHECK
            if is_blocked(html):
                time.sleep(random.uniform(1, 2))
                continue

            rating, reviews = extract_data(html)
            title, price = extract_title_price(html)

            if title:
                last_title = title

            if price:
                last_price = price

            # ✅ SUCCESS IF RATING FOUND
            if rating > 0:
                return {
                    "asin": asin,
                    "rating": rating,
                    "reviews": reviews,
                    "title": last_title,
                    "price": last_price
                }

        except:
            pass

        # ⏳ SMALL RANDOM DELAY
        time.sleep(random.uniform(0.5, 1.5))

    # Final fallback:
    # If title + price were visible during retries,
    # accept rating/reviews as 0
    if last_title and last_price:
        return {
            "asin": asin,
            "rating": 0,
            "reviews": 0,
            "title": last_title,
            "price": last_price
        }

    # ❌ FAIL
    return {
        "asin": asin,
        "rating": 0,
        "reviews": 0,
        "title": "",
        "price": ""
    }

# 🚀 API ENDPOINT
@app.get("/batch_amazon")
def batch_amazon(asins: str):

    asin_list = asins.split(",")
    results = []

    for asin in asin_list:

        asin = asin.strip()

        if not asin:
            continue

        data = fetch_amazon(asin)

        # 🔁 SECOND LAYER RETRY ONLY IF NOTHING WAS FOUND
        if (
            data["rating"] == 0 and
            data["reviews"] == 0 and
            not data["title"] and
            not data["price"]
        ):
            time.sleep(1)
            data = fetch_amazon(asin)

        results.append(data)

    return results
