from fastapi import FastAPI
import requests
import random
from bs4 import BeautifulSoup

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edg/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 Version/15.0 Mobile Safari/604.1"
]

def is_blocked(html):
    text = html.lower()

    return (
        "captcha" in text or
        "robot check" in text or
        "enter the characters you see below" in text or
        "sorry, we just need to make sure you're not a robot" in text or
        len(html) < 3000
    )

def extract_data(html):
    soup = BeautifulSoup(html, "html.parser")

    rating = 0
    reviews = 0
    title = ""
    price = ""

    # Product title
    title_selectors = [
        "#productTitle",
        "#title",
        "span#productTitle"
    ]

    for selector in title_selectors:
        title_tag = soup.select_one(selector)
        if title_tag:
            title = title_tag.get_text(strip=True)
            if title:
                break

    # Selling price
    price_selectors = [
        ".a-price-whole",
        "span.a-price-whole",
        ".reinventPricePriceToPayMargin span.a-offscreen",
        ".a-price .a-offscreen"
    ]

    for selector in price_selectors:
        price_tag = soup.select_one(selector)
        if price_tag:
            price = price_tag.get_text(strip=True)
            if price:
                break

    # Rating
    rating_tag = soup.select_one("#acrPopover")
    if rating_tag:
        title_attr = rating_tag.get("title", "")
        if "out of" in title_attr:
            try:
                rating = float(title_attr.split(" ")[0])
            except:
                pass

    if rating == 0:
        alt_rating_selectors = [
            "span[data-hook='rating-out-of-text']",
            ".a-icon-alt"
        ]

        for selector in alt_rating_selectors:
            alt_rating = soup.select_one(selector)
            if alt_rating:
                text = alt_rating.get_text(strip=True)
                if "out of" in text:
                    try:
                        rating = float(text.split(" ")[0])
                        break
                    except:
                        pass

    # Reviews
    review_tag = soup.select_one("#acrCustomerReviewText")
    if review_tag:
        text = review_tag.get_text(strip=True)
        num = ''.join(filter(str.isdigit, text))
        if num:
            reviews = int(num)

    if reviews == 0:
        alt_review_selectors = [
            "span[data-hook='total-review-count']",
            "#reviews-medley-footer .a-link-normal"
        ]

        for selector in alt_review_selectors:
            alt_review = soup.select_one(selector)
            if alt_review:
                text = alt_review.get_text(strip=True)
                num = ''.join(filter(str.isdigit, text))
                if num:
                    reviews = int(num)
                    break

    return {
        "rating": rating,
        "reviews": reviews,
        "title": title,
        "price": price
    }

def fetch_amazon(asin):
    url = f"https://www.amazon.in/dp/{asin}"

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

        if is_blocked(html):
            return {
                "asin": asin,
                "rating": 0,
                "reviews": 0,
                "title": "",
                "price": "",
                "status": "blocked"
            }

        extracted = extract_data(html)

        title = extracted["title"]
        price = extracted["price"]
        rating = extracted["rating"]
        reviews = extracted["reviews"]

        # If title and price exist, page is valid even if rating/reviews are 0
        if title and price:
            return {
                "asin": asin,
                "rating": rating,
                "reviews": reviews,
                "title": title,
                "price": price,
                "status": "success"
            }

        # If page is incomplete
        return {
            "asin": asin,
            "rating": 0,
            "reviews": 0,
            "title": title,
            "price": price,
            "status": "partial"
        }

    except Exception as e:
        return {
            "asin": asin,
            "rating": 0,
            "reviews": 0,
            "title": "",
            "price": "",
            "status": "error",
            "error": str(e)
        }

@app.get("/batch_amazon")
def batch_amazon(asins: str):

    asin_list = [a.strip() for a in asins.split(",") if a.strip()]
    results = []

    for asin in asin_list:
        results.append(fetch_amazon(asin))

    return results
