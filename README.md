
# Indian Market Sentiment Analyzer (Twitter/X)

This project is a Python-based system that collects and analyzes Indian stock market discussions from X (Twitter) and converts them into a quantitative sentiment signal.

The objective is to demonstrate **data collection, processing, and signal generation** under real-world constraints such as rate limiting, noisy text, and Indian market language.

---

## Project Overview

Retail sentiment on social media often reflects short-term market mood, especially in Indian equities.
This system focuses on:

* Collecting recent market-related tweets without using paid APIs
* Cleaning and normalizing noisy text data
* Handling Hindi and Hinglish market language
* Converting text into numerical signals usable for algorithmic trading research

The output is a **time-series sentiment signal ranging from -1.0 to +1.0**.

---

## Key Features

### Data Collection

* Scrapes tweets related to Indian markets (`#nifty50`, `#sensex`, `#banknifty`, `#intraday`)
* Uses Selenium (no paid APIs)
* Extracts username, timestamp, tweet text, hashtags, mentions, and engagement metrics

### Data Processing & Storage

* Cleans and normalizes raw tweet data
* Handles Unicode, Hindi, and Hinglish text
* Removes duplicates efficiently
* Stores processed data in **Parquet format** for memory-efficient access

### Sentiment Analysis & Signal Generation

* Keyword-based financial sentiment scoring
* TF-IDF–based semantic scoring
* Combines multiple signals into a single weighted sentiment score
* Uses bootstrapping to calculate confidence intervals and filter low-confidence signals

---

## Challenges Faced During Scraping

Scraping X (Twitter) introduces several practical challenges:

* **Scroll limits and DOM throttling:**
  After loading a few hundred tweets, the page stops returning new content and browser memory usage increases.

* **Rate limiting and bot detection:**
  Repeated requests using the same query pattern can lead to temporary blocks or empty responses.

* **Dynamic content loading:**
  Tweets load asynchronously, requiring careful wait conditions and defensive error handling.

* **No API access:**
  The assignment constraint of not using paid APIs required handling all data collection through browser automation.

### Approach Used

* Rotated across multiple market-related keywords instead of relying on a single hashtag
* Periodically refreshed the browser context to reset DOM state
* Used time-based search slicing (`since` / `until`) to retrieve older tweets without deep scrolling
* Added randomized delays and retry logic to reduce detection risk

These techniques helped maintain stable data collection while staying within the assignment constraints.

---

## Repository Structure

```text
repo/
│
├── src/
│   ├── collection.py        # Twitter/X scraping logic (Selenium)
│   ├── processing.py        # Data cleaning, normalization, deduplication
│   └── analysis.py          # Sentiment analysis and signal generation
│
├── sample/
│   ├── csv_data/            # Sample raw scraped CSV files
│   ├── parquet_data/        # Sample processed Parquet files
│   └── signal_data/         # Sample sentiment signals and plots
│
├── main.py                  # End-to-end pipeline runner
├── requirements.txt
└── README.md
```

---

## Setup & Usage

### Requirements

* Python 3.11+
* Google Chrome (latest version)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Full Pipeline

```bash
python main.py
```

### Run Individual Modules

```bash
python src/collection.py     # Data collection
python src/processing.py     # Data processing
python src/analysis.py       # Sentiment analysis
```

---

## Output

* Cleaned and deduplicated market tweet dataset (Parquet)
* Time-series sentiment signal (`-1.0` to `+1.0`)
* Visualization showing:

  * Keyword-based sentiment
  * Semantic sentiment
  * Final combined signal

Sample outputs are available in the `samples/` directory.

---

## Design Decisions (Brief)

* Selenium used to comply with the “no paid API” requirement
* Query rotation and time slicing implemented to handle rate limits and scrolling constraints
* Parquet chosen for efficient storage and scalability
* Custom sentiment logic added to support Indian market language

---

## Scalability Considerations

For larger workloads:

* Store data on object storage (e.g., S3)
* Run scraping jobs on scheduled or serverless infrastructure
* Store final signals in a time-series database for fast retrieval

---

## Notes

* Built as part of a technical assessment
* Intended for research and analysis purposes only


