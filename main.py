from fastapi import FastAPI
import requests
import random
import time
from bs4 import BeautifulSoup

app = FastAPI()

USER_AGENTS = [
"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119 Safari/537.36",
"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/118 Safari/537.36",
]

def is_blocked(html):
text = html.lower()
return (
"captcha" in text or
"robot check" in text or
len(html) < 5000
)

def extract_data(html, asin):
soup = BeautifulSoup(html, "html.parser")


rating = 0
reviews = 0

# STRICT SELECTORS
rating_tag = soup.select_one("#acrPopover")
if rating_tag:
    title = rating_tag.get("title", "")
    if "out of" in title:
        try:
            rating = float(title.split(" ")[0])
        except:
            pass

review_tag = soup.select_one("#acrCustomerReviewText")
if review_tag:
    text = review_tag.text.strip()
    num = ''.join(filter(str.isdigit, text))
    if num:
        reviews = int(num)

return rating, reviews


def fetch_amazon(asin):


url = f"https://www.amazon.in/dp/{asin}"

for attempt in range(5):  # 🔥 5 attempts (strong)

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-IN,en;q=0.9",
        "Referer": "https://www.amazon.in/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        html = response.text

        # 🚨 BLOCK DETECTION
        if is_blocked(html):
            time.sleep(random.uniform(2, 4))
            continue

        # 🔍 EXTRACT
        rating, reviews = extract_data(html, asin)

        # ✅ SUCCESS
        if rating > 0:
            return {
                "asin": asin,
                "rating": rating,
                "reviews": reviews
            }

    except:
        pass

    # ⏳ RANDOM DELAY
    time.sleep(random.uniform(1.5, 3.5))

# ❌ FINAL FAIL
return {
    "asin": asin,
    "rating": 0,
    "reviews": 0
}


@app.get("/batch_amazon")
def batch_amazon(asins: str):


asin_list = asins.split(",")
results = []

for asin in asin_list:

    data = fetch_amazon(asin)

    # 🔁 SECOND LEVEL RETRY (VERY IMPORTANT)
    if data["rating"] == 0:
        time.sleep(2)
        data = fetch_amazon(asin)

    results.append(data)

return results

