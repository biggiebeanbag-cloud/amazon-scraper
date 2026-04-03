from fastapi import FastAPI
import requests
import random
import time
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

session = requests.Session()


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

    rating_tag = soup.select_one("#acrPopover")
    if rating_tag:
        title = rating_tag.get("title", "")
        if "out of" in title:
            try:
                rating = float(title.split(" ")[0].replace(",", "."))
            except:
                pass

    if rating == 0:
        rating_tag = soup.select_one("span[data-hook='rating-out-of-text']")
        if rating_tag:
            try:
                rating = float(rating_tag.text.split(" ")[0].replace(",", "."))
            except:
                pass

    review_tag = soup.select_one("#acrCustomerReviewText")
    if review_tag:
        text = review_tag.text.strip()
        num = ''.join(filter(str.isdigit, text))
        if num:
            reviews = int(num)

    if reviews == 0:
        review_tag = soup.select_one("span[data-hook='total-review-count']")
        if review_tag:
            num = ''.join(filter(str.isdigit, review_tag.text))
            if num:
                reviews = int(num)

    return rating, reviews


def fetch_amazon(asin):
    url = f"https://www.amazon.in/dp/{asin}"

    for attempt in range(3):

        headers = {
    return results
