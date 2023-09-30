# politics_rss_collection.py

import os
import json
import requests
import feedparser
import logging
import re
import html
from datetime import datetime, timezone
from dateutil import parser
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(level=logging.INFO)

# Constants
SQUABBLES_TOKEN = os.environ.get('POL_SQUABBLR_TOKEN')
GIST_TOKEN = os.environ.get('DNDBLOGS_GIST_TOKEN')
GIST_ID_TRACKER = '5b6ca1c95d1ebf399def37898589616a'
GIST_ID_DETAILS = '6c90a5d9642610efdbf83840dfc0fb76'
FILE_NAME_TRACKER = 'politics-rss-tracker.json'
FILE_NAME_DETAILS = 'politics-article-details.json'
GIST_URL_TRACKER = f"https://gist.githubusercontent.com/amightybeard/{GIST_ID_TRACKER}/raw/{FILE_NAME_TRACKER}"
GIST_URL_DETAILS = f"https://gist.githubusercontent.com/amightybeard/{GIST_ID_DETAILS}/raw/{FILE_NAME_DETAILS}"

def parse_date_to_datetime(date_str):
    """
    Parse a date string using dateutil's parser.
    If the datetime is offset-naive, default to UTC.
    Returns a datetime object.
    """
    dt = parser.parse(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # Default to UTC
    return dt

def parse_date_to_iso(date_str):
    """
    Parse a date string using dateutil's parser.
    If the datetime is offset-naive, default to UTC.
    Returns date in ISO format.
    """
    return parse_date_to_datetime(date_str).isoformat()

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
            article_date = parse_date_to_datetime(article_date_str)
        else:
            continue  # Skip this entry and move to the next
        if article_date > last_fetched_date:
            description_raw = entry.get("description", "")
            
            # Special handling for ProPublica.org descriptions
            if blog["blog_name"] == "ProPublica.org":
                soup = BeautifulSoup(description_raw, 'html.parser')
                description_cleaned = ' '.join([p.text for p in soup.find_all('p', {'data-pp-blocktype': 'copy'})])
            else:
                description_cleaned = re.sub('<[^<]+?>', '', description_raw)  # Remove HTML tags
            
            # Further cleaning for all descriptions
            description_cleaned = html.unescape(description_cleaned)  # Convert HTML entities to characters
            description_cleaned = description_cleaned.replace("&nbsp;", " ")  # Replace non-breaking spaces with regular spaces
            description_cleaned = re.sub(' +', ' ', description_cleaned)  # Replace multiple spaces with a single space
            description_cleaned = description_cleaned.strip()  # Remove leading and trailing whitespaces
            
            new_articles.append({
                "blog_name": blog["blog_name"],
                "url": entry.link,
                "title": entry.title,
                "description": description_cleaned,
                "date_published": parse_date_to_iso(article_date_str),
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

# Sort articles by date_published in ascending order
updated_articles.sort(key=lambda x: x["date_published"])

# Update politics-article-details.json gist with the new articles
logging.info("Updating politics-article-details.json with new articles...")
payload = {
    "files": {
        FILE_NAME_DETAILS: {
            "content": json.dumps(updated_articles, indent=4)
        }
    }
}
response = requests.patch(f"https://api.github.com/gists/{GIST_ID_DETAILS}", headers=headers, json=payload)
logging.info("politics-article-details.json updated successfully.")

# Update the last fetched date
logging.info("Updating last fetched date in politics-rss-tracker.json...")
rss_tracker_data["last_fetched"] = datetime.now().strftime('%Y-%m-%d')
payload = {
    "files": {
        FILE_NAME_TRACKER: {
            "content": json.dumps(rss_tracker_data, indent=4)
        }
    }
}
response = requests.patch(f"https://api.github.com/gists/{GIST_ID_TRACKER}", headers=headers, json=payload)
logging.info("Last fetched date updated successfully.")

logging.info(f"Bot completed. {len(new_articles)} new articles added.")
