# nflblogs_rss_collection.py

import os
import json
import requests
import feedparser
import logging
from datetime import datetime, timezone
from dateutil import parser

# Setup logging
logging.basicConfig(level=logging.INFO)

# Constants
SQUABBLES_TOKEN = os.environ.get('NFLBLOGS_SQUABBLR_TOKEN')
GIST_TOKEN = os.environ.get('NFLBLOGS_GIST_TOKEN')
GIST_ID_TRACKER = os.environ.get('NFLBLOGS_GIST_TRACKER')
GIST_ID_DETAILS = os.environ.get('NFLBLOGS_GIST_DETAILS')
FILE_NAME_TRACKER = 'NFLblogs-rss-tracker.json'
FILE_NAME_DETAILS = 'NFLblogs-article-details.json'
GIST_URL_TRACKER = f"https://gist.githubusercontent.com/amightybeard/{GIST_ID_TRACKER}/raw/{FILE_NAME_TRACKER}"
GIST_URL_DETAILS = f"https://gist.githubusercontent.com/amightybeard/{GIST_ID_DETAILS}/raw/{FILE_NAME_DETAILS}"

def parse_date(date_str):
    """
    Parse a date string using dateutil's parser.
    If the datetime is offset-naive, default to UTC.
    """
    dt = parser.parse(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # Default to UTC
    return dt

logging.info("Fetching tracker data...")
response = requests.get(GIST_URL_TRACKER)
rss_tracker_data = response.json()
last_fetched_date = datetime.strptime(rss_tracker_data["last_fetched"], '%Y-%m-%d').replace(tzinfo=timezone.utc)
logging.info("Tracker data fetched successfully.")

new_articles = []

# Fetch and parse RSS feeds for new articles
logging.info("Starting RSS feed parsing...")
for blog in rss_tracker_data["blogs"]:
    feed = feedparser.parse(blog["rss_url"])
    for entry in feed.entries:
        article_date_str = entry.published.split("T")[0] if "T" in entry.published else entry.published

        if article_date_str:
            article_date = parse_date(article_date_str)
        else:
            continue  # Skip this entry and move to the next

        if article_date > last_fetched_date:
            new_articles.append({
                "blog_name": blog["blog_name"],
                "url": entry.link,
                "title": entry.title,
                "date_published": entry.published,
                "posted": False
            })
logging.info(f"RSS feed parsing completed. Found {len(new_articles)} new articles.")

# Get existing articles and append new ones
logging.info("Fetching existing articles...")
headers = {
    "Authorization": f"token {GIST_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
response = requests.get(GIST_URL_DETAILS, headers=headers)
existing_articles = response.json()
logging.info("Existing articles fetched successfully.")

updated_articles = existing_articles + new_articles

# Update nflblogs-article-details.json gist with the new articles
logging.info("Updating nflblogs-article-details.json with new articles...")
payload = {
    "files": {
        FILE_NAME_DETAILS: {
            "content": json.dumps(updated_articles, indent=4)
        }
    }
}
response = requests.patch(f"https://api.github.com/gists/{GIST_ID_DETAILS}", headers=headers, json=payload)
logging.info("nflblogs-article-details.json updated successfully.")

# Update the last fetched date
logging.info("Updating last fetched date in nflblogs-rss-tracker.json...")
rss_tracker_data["last_fetched"] = datetime.now().strftime('%Y-%m-%d')
payload = {
    "files": {
        FILE_NAME_TRACKER: {
            "content": json.dumps(rss_tracker_data)
        }
    }
}
response = requests.patch(f"https://api.github.com/gists/{GIST_ID_TRACKER}", headers=headers, json=payload)
logging.info("Last fetched date updated successfully.")

logging.info(f"Bot completed. {len(new_articles)} new articles added.")
