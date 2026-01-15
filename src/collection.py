"""
X (Twitter) Scraper for Market Sentiment Analysis.

This module implements a  scraping strategy to collect financial tweets
without hitting standard rate limits. It uses query rotation, time-window slicing,
and human-like interaction patterns to bypass anti-bot detection.
"""

import time
import random
import re
import logging
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from urllib.parse import quote
from collections import deque

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

TARGET = 2000
CHECKPOINT_EVERY = 100

MAX_TWEETS_PER_QUERY = 150
MIN_TWEETS_PER_QUERY = 30

FAST_SCROLL_WAIT = (0.5, 1.2)
SLOW_SCROLL_WAIT = (2.0, 4.0)
SCROLL_PIXELS = (800, 1800)

OUTPUT_DIR = Path("data/raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUTPUT_DIR / "tweets_2k.csv"
PARTIAL_CSV = OUTPUT_DIR / "tweets_2k_partial.csv"

# Pool of correlated keywords to rotate through to avoid single-query blocking
QUERY_POOL = [
    "#nifty50",
    "#nifty",
    "#sensex",
    "#banknifty",
    "#stockmarket",
    "#nse",
    "#bse",
    "nifty trading",
    "nifty analysis",
    "sensex market",
    "bank nifty options",
    "nifty futures",
    "sensex today",
    "stock market india",
    "nifty levels",
    "nifty targets",
    "sensex movement",
    "banknifty strategy",
    "options trading nifty",
    "nifty chart",
    "market analysis india",
    "$NIFTY",
    "$BANKNIFTY",
    "$SENSEX",
    "nifty50 trading",
    "sensex analysis",
    "banknifty levels",
    "indian stocks nifty",
    "nse trading",
]

# Time windows (in days) to force the scraper to fetch different data slices
TIME_WINDOWS = [1, 2, 3, 5, 7]


def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = log_dir / f"x_scraper_2k_{ts}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    logging.info(f"Log: {log_file}")


def log(msg):
    logging.info(msg)


def build_driver():
    """
    Initializes a Chrome Selenium driver with anti-detection overrides.

    Strategies used:
    - Disables 'navigator.webdriver' flag to hide from bot detection.
    - Connects to local debugger port (9222) if available for persistence.

    Returns:
        webdriver.Chrome: The configured browser instance.
    """

    opts = Options()
    opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=opts)

    driver.execute_script(
        """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    """
    )

    log("Driver ready")
    return driver


def human_scroll(driver, is_stalled=False):
    """
    Simulates human-like scrolling behavior with randomized pauses and pixel offsets.

    Args:
        driver: The active Selenium webdriver.
        is_stalled (bool): If True, triggers a larger scroll jump to unfreeze the DOM.
    """
    if is_stalled:
        pixels = random.randint(2000, 3500)
        driver.execute_script(f"window.scrollBy(0, {pixels});")
        time.sleep(random.uniform(*SLOW_SCROLL_WAIT))
    else:
        pixels = random.randint(*SCROLL_PIXELS)
        driver.execute_script(f"window.scrollBy(0, {pixels});")
        time.sleep(random.uniform(*FAST_SCROLL_WAIT))

    if random.random() < 0.05:
        driver.execute_script(f"window.scrollBy(0, -{random.randint(50, 150)});")
        time.sleep(random.uniform(0.2, 0.5))


def safe_text(el, css):
    """Safely extracts text from a WebElement, returning empty string on failure."""
    try:
        return el.find_element(By.CSS_SELECTOR, css).text.strip()
    except:
        return ""


def safe_attr(el, css, attr):
    """Safely extracts an attribute from a WebElement, returning None on failure."""
    try:
        return el.find_element(By.CSS_SELECTOR, css).get_attribute(attr)
    except:
        return None


def parse_count(s: str) -> int:
    """Parses social metric strings (e.g., '1.2K') into integers."""
    s = (s or "").replace(",", "").strip()
    if not s:
        return 0
    mult = 1
    if s.endswith("K"):
        mult, s = 1000, s[:-1]
    elif s.endswith("M"):
        mult, s = 1_000_000, s[:-1]
    try:
        return int(float(s) * mult)
    except:
        return 0


def parse_ts(ts: str):
    """Parses ISO timestamp string into a datetime object."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except:
        return None


def build_url(query: str, days_back: int) -> str:
    """Builds a Twitter search URL with a time window constraint."""
    since_date = (date.today() - timedelta(days=days_back)).isoformat()
    q = f"({query}) since:{since_date}"
    return f"https://x.com/search?q={quote(q)}&src=typed_query&f=live"


def checkpoint(rows):
    """Saves collected tweets to a partial CSV file."""
    try:
        pd.DataFrame(rows).to_csv(PARTIAL_CSV, index=False, encoding="utf-8")
        log(f"Checkpoint: {len(rows)} tweets")
    except Exception as e:
        log(f"Checkpoint failed: {e}")


def metric_count(article, testid_options):
    """Extracts a social metric count from an article element."""
    for tid in testid_options:
        try:
            el = article.find_element(By.CSS_SELECTOR, f'[data-testid="{tid}"]')
            txt = (el.text or "").strip()
            if txt:
                return parse_count(txt)
            for sp in el.find_elements(By.CSS_SELECTOR, "span"):
                t = (sp.text or "").strip()
                if t:
                    return parse_count(t)
        except:
            continue
    return 0


def extract_username(article):
    """Extracts the Twitter username from an article element."""
    block = safe_text(article, '[data-testid="User-Name"]')
    if block:
        m = re.search(r"@\w+", block)
        if m:
            return m.group(0)
        return block.splitlines()[0].strip()
    return ""


def extract_tweet(article, cutoff_time):
    """Extracts tweet details from an article element."""
    try:
        ts_raw = safe_attr(article, "time", "datetime")
        ts = parse_ts(ts_raw)
        if not ts or ts < cutoff_time:
            return "OLD"

        links = article.find_elements(By.CSS_SELECTOR, 'a[href*="/status/"]')
        if not links:
            return None
        url = (links[0].get_attribute("href") or "").split("?")[0]
        if not url or "/status/" not in url:
            return None

        content = safe_text(article, '[data-testid="tweetText"]')
        username = extract_username(article)

        if not content or len(content) < 20:
            return None

        content_lower = content.lower()
        spam_keywords = [
            "t.me/",
            "wa.me/",
            "whatsapp",
            "telegram",
            "join channel",
            "join group",
        ]
        if any(kw in content_lower for kw in spam_keywords):
            return None

        username_lower = (username or "").lower()
        bot_indicators = ["bot", "alert", "signal", "algo"]
        if any(ind in username_lower for ind in bot_indicators):
            return None

        return {
            "tweet_id": url.split("/")[-1],
            "username": username,
            "timestamp_utc": ts_raw,
            "content": content,
            "like_count": metric_count(article, ["like"]),
            "retweet_count": metric_count(article, ["retweet", "repost"]),
            "reply_count": metric_count(article, ["reply"]),
            "hashtags": ",".join(re.findall(r"#\w+", content)),
            "mentions": ",".join(re.findall(r"@\w+", content)),
            "url": url,
        }
    except:
        return None


def scrape_query(
    driver,
    query_label: str,
    query: str,
    days_back: int,
    rows,
    seen_ids,
    target_total: int,
):
    """Scrapes tweets for a specific query and time window."""
    url = build_url(query, days_back)
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_back)

    log(
        f"Query {query_label}: {query} ({days_back}d) | Need: {target_total - len(rows)} | Current: {len(rows)}/{target_total}"
    )

    driver.get(url)
    time.sleep(random.uniform(3, 5))

    scrolls = 0
    no_new_count = 0
    stall_count = 0
    prev_dom = 0

    query_start = time.time()
    tweets_at_start = len(rows)
    tweets_this_query = 0

    while len(rows) < target_total and tweets_this_query < MAX_TWEETS_PER_QUERY:
        articles = driver.find_elements(By.CSS_SELECTOR, "article")
        dom_count = len(articles)

        if scrolls == 0 and dom_count < 5:
            log(f"Low DOM ({dom_count}) - may be limited")

        new_this_batch = 0
        window = articles[-120:] if len(articles) > 120 else articles

        for art in window:
            data = extract_tweet(art, cutoff_time)
            if data == "OLD":
                continue
            if not data:
                continue

            tid = data["tweet_id"]
            if tid in seen_ids:
                continue

            seen_ids.add(tid)
            data["query"] = query_label
            data["days_back"] = days_back
            rows.append(data)
            new_this_batch += 1
            tweets_this_query += 1

        if scrolls % 20 == 0 and scrolls > 0:
            elapsed = int(time.time() - query_start)
            rate = tweets_this_query / max(elapsed, 1) * 60
            log(
                f"{scrolls} scrolls | +{tweets_this_query} tweets | {rate:.1f}/min | DOM:{dom_count}"
            )

        if new_this_batch > 0 and (len(rows) // CHECKPOINT_EVERY) > (
            (len(rows) - new_this_batch) // CHECKPOINT_EVERY
        ):
            checkpoint(rows)

        if new_this_batch == 0:
            no_new_count += 1
            if dom_count <= prev_dom:
                stall_count += 1
            else:
                stall_count = 0
        else:
            no_new_count = 0
            stall_count = 0

        prev_dom = dom_count

        if tweets_this_query >= MAX_TWEETS_PER_QUERY:
            log(f"Hit limit: {tweets_this_query} tweets (switching query)")
            break

        if no_new_count >= 15:
            if tweets_this_query < MIN_TWEETS_PER_QUERY:
                log(f"Low yield: {tweets_this_query} tweets (query exhausted)")
            else:
                log(f"Done: {tweets_this_query} tweets")
            break

        if stall_count >= 5:
            log(f"Refresh (stalled)")
            driver.refresh()
            time.sleep(random.uniform(3, 5))
            stall_count = 0
            continue

        is_stalled = new_this_batch == 0
        human_scroll(driver, is_stalled)
        scrolls += 1

    return tweets_this_query


def main():
    """Main function to execute the scraper."""
    setup_logging()
    log("=" * 80)
    log("SCRAPER STARTED For X")
    log(
        f"Target: {TARGET} tweets | Queries: {len(QUERY_POOL)} | Time windows: {len(TIME_WINDOWS)}"
    )
    log("=" * 80)

    driver = build_driver()
    rows = []
    seen_ids = set()
    start_time = time.time()

    query_performance = {}

    queries = QUERY_POOL.copy()
    random.shuffle(queries)

    query_index = 0

    try:
        while len(rows) < TARGET and query_index < len(queries) * len(TIME_WINDOWS):
            query = queries[query_index % len(queries)]
            days_back = TIME_WINDOWS[query_index % len(TIME_WINDOWS)]

            label = f"{query_index+1:02d}"

            tweets_found = scrape_query(
                driver, label, query, days_back, rows, seen_ids, TARGET
            )

            key = f"{query}_{days_back}d"
            query_performance[key] = tweets_found

            query_index += 1

            if len(rows) < TARGET:
                wait = random.uniform(2, 5)
                time.sleep(wait)

            if query_index % 5 == 0:
                elapsed = int(time.time() - start_time)
                rate = len(rows) / max(elapsed / 60, 1)
                log(
                    f"PROGRESS: {len(rows)}/{TARGET} tweets | {elapsed//60}m {elapsed%60}s | {rate:.1f}/min"
                )

        elapsed = int(time.time() - start_time)
        rate = len(rows) / max(elapsed / 60, 1)

        log("=" * 80)
        log(
            f"COMPLETE: {len(rows)} tweets in {elapsed//60}m {elapsed%60}s ({rate:.1f}/min)"
        )
        log("=" * 80)

    except KeyboardInterrupt:
        log("Stopped by user")
    except Exception as e:
        log(f"Error: {e}")
        import traceback

        log(traceback.format_exc())
    finally:
        if rows:
            df = pd.DataFrame(rows).drop_duplicates("tweet_id")
            df.to_csv(OUT_CSV, index=False, encoding="utf-8")

            elapsed = int(time.time() - start_time)
            rate = len(df) / max(elapsed / 60, 1)

            log("=" * 80)
            log(f"SAVED: {len(df)} unique tweets to {OUT_CSV}")
            log(f"Time: {elapsed//60}m {elapsed%60}s | Rate: {rate:.1f}/min")
            log("=" * 80)

            log(f"Unique users: {df['username'].nunique()}")
            log(f"With hashtags: {df['hashtags'].str.len().gt(0).sum()}")
            log(f"Avg engagement: {df['like_count'].mean():.1f} likes")
            log(
                f"Date range: {df['timestamp_utc'].min()[:10]} to {df['timestamp_utc'].max()[:10]}"
            )

            log("TOP 10 QUERIES:")
            sorted_perf = sorted(
                query_performance.items(), key=lambda x: x[1], reverse=True
            )
            for query, count in sorted_perf[:10]:
                log(f"   {query}: {count} tweets")
        else:
            log("No tweets collected")

        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    main()
