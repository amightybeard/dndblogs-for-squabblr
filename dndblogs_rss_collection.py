import requests
import os
import json
import logging
import io
from datetime import datetime
import xml.etree.ElementTree as ET

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Constants
SQUABBLES_TOKEN = os.environ.get('DNDBLOGS_SQUABBLR_TOKEN')
GIST_TOKEN =  os.environ.get('DNDBLOGS_GIST_TOKEN')
GIST_ID_TRACKER = os.environ.get('DNDBLOGS_GIST_TRACKER')
FILE_NAME_TRACKER = 'dndblogs-rss-tracker.json'
GIST_URL_TRACKER = f"https://gist.githubusercontent.com/amightybeard/{GIST_ID_TRACKER}/raw/{FILE_NAME_TRACKER}"
DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def fetch_gist_data(gist_id, token):
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    gist_url = f"https://api.github.com/gists/{GIST_ID_TRACKER}"
    response = requests.get(gist_url, headers=headers)
    response.raise_for_status()
    gist_content = list(response.json()["files"].values())[0]["content"]
    return json.loads(gist_content)

def update_tracker_gist(blog_name, new_date, gist_id, token):
    current_data = fetch_gist_data(gist_id, token)
    for entry in current_data:
        if entry["blog_name"] == blog_name:
            entry["last_fetched"] = new_date
            break
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    gist_url = f"https://api.github.com/gists/{GIST_ID_TRACKER}"
    updated_content = json.dumps(current_data, indent=4)
    data = {
        "files": {
            "{FILE_NAME_TRACKER}": {
                "content": updated_content
            }
        }
    }
    response = requests.patch(gist_url, headers=headers, json=data)
    response.raise_for_status()
    return response.status_code

def add_article_to_details_gist(url, title, date_published, gist_id, token):
    current_data = fetch_gist_data(gist_id, token)
    new_article = {
        "url": url,
        "title": title,
        "date_published": date_published,
        "posted": False
    }
    current_data.append(new_article)
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    gist_url = f"https://api.github.com/gists/{GIST_ID_DETAILS}"
    updated_content = json.dumps(current_data, indent=4)
    data = {
        "files": {
            "{FILE_NAME_DETAILS}": {
                "content": updated_content
            }
        }
    }
    response = requests.patch(gist_url, headers=headers, json=data)
    response.raise_for_status()
    return response.status_code

def fetch_rss_articles_since_date_xml(rss_url, since_date):
    response = requests.get(rss_url)
    root = ET.fromstring(response.content)
    namespace = {"ns": "http://purl.org/dc/elements/1.1/"}
    articles = []
    for item in root.findall(".//item"):
        pub_date_text = item.find("pubDate").text if item.find("pubDate") is not None else item.find("ns:date", namespace).text
        try:
            pub_date = datetime.strptime(pub_date_text, "%a, %d %b %Y %H:%M:%S %Z")
        except:
            pub_date = datetime.strptime(pub_date_text, "%Y-%m-%dT%H:%M:%SZ")
        if pub_date.strftime("%Y-%m-%d") > since_date:
            articles.append({
                "url": item.find("link").text,
                "title": item.find("title").text,
                "date_published": pub_date.strftime("%Y-%m-%d")
            })
    return articles

if __name__ == "__main__":
    pass