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
GIST_ID_DETAILS = os.environ.get('DNDBLOGS_GIST_DETAILS')
FILE_NAME_TRACKER = 'dndblogs-rss-tracker.json'
FILE_NAME_DETAILS = 'dndblogs-article-details.json'
GIST_URL_TRACKER = f"https://gist.githubusercontent.com/amightybeard/{GIST_ID_TRACKER}/raw/{FILE_NAME_TRACKER}"
GIST_URL_DETAILS = f"https://gist.githubusercontent.com/amightybeard/{GIST_ID_DETAILS}/raw/{FILE_NAME_DETAILS}"
DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def fetch_gist_data(gist_id, token):
    logging.info(f"Fetching data from gist: {gist_id}")
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
    logging.info(f"Updating tracker gist for blog: {blog_name} with date: {new_date}")
    current_data = fetch_gist_data(GIST_ID_DETAILS, GIST_TOKEN)
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
            "dndblogs-rss-tracker.json": {
                "content": updated_content
            }
        }
    }
    response = requests.patch(gist_url, headers=headers, json=data)
    response.raise_for_status()
    return response.status_code

def add_article_to_details_gist(url, title, date_published, gist_id, token):
    logging.info(f"Adding article with title: {title} and {url} to details gist")
    current_data = fetch_gist_data(gist_id, token)
    new_article = {
        "url": url,
        "title": title,
        "date_published": date_published,
        "posted": False
    }
    current_data.append(new_article)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    gist_url = f"https://api.github.com/gists/{gist_id}"
    updated_content = json.dumps(current_data, indent=4)
    data = {
        "files": {
            "dndblogs-article-details.json": {
                "content": updated_content
            }
        }
    }
    response = requests.patch(gist_url, headers=headers, json=data)
    response.raise_for_status()
    return response.status_code

def fetch_rss_articles_since_date_xml(rss_url, since_date):
    response = requests.get(rss_url)
    articles = []
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        logging.error(f"Error parsing XML from RSS feed: {rss_url}")
        logging.debug(f"Content of problematic RSS feed:\n{response.text}")
        return articles

    namespace = {"ns": "http://purl.org/dc/elements/1.1/"}
    for item in root.findall(".//item"):
        pub_date_text = item.find("pubDate").text if item.find("pubDate") is not None else item.find("ns:date", namespace).text
        try:
            pub_date = datetime.strptime(pub_date_text, "%a, %d %b %Y %H:%M:%S %Z")
        except ValueError:
            try:
                pub_date = datetime.strptime(pub_date_text, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                try:
                    pub_date = datetime.strptime(pub_date_text, "%a, %d %b %Y %H:%M:%S %z")
                except ValueError:
                    logging.error(f"Unable to parse date: {pub_date_text}")
                    continue
        if pub_date.strftime("%Y-%m-%d") > since_date:
            articles.append({
                "url": item.find("link").text,
                "title": item.find("title").text,
                "date_published": pub_date.strftime("%Y-%m-%d")
            })
    return articles

if __name__ == "__main__":
    logging.info("Script started.")
    
    # Fetch the current tracker data
    tracker_data = fetch_gist_data(GIST_ID_TRACKER, GIST_TOKEN)
    
    for blog in tracker_data:
        blog_name = blog["blog_name"]
        rss_url = blog["rss_url"]
        last_fetched = blog["last_fetched"]
        
        logging.info(f"Processing articles for blog: {blog_name} since {last_fetched}")
        
        # Fetch new articles since the last fetched date
        new_articles = fetch_rss_articles_since_date_xml(rss_url, last_fetched)
        
        # If there are new articles, process them
        if new_articles:
            latest_date = last_fetched
            
            for article in new_articles:
                add_article_to_details_gist(article["url"], article["title"], article["date_published"], GIST_ID_DETAILS, GIST_TOKEN)
                # Update the latest date if the current article's date is more recent
                if article["date_published"] > latest_date:
                    latest_date = article["date_published"]
            
            # Update the tracker gist with the most recent date
            update_tracker_gist(blog_name, latest_date, GIST_ID_TRACKER, GIST_TOKEN)
        
        else:
            logging.info(f"No new articles found for blog: {blog_name} since {last_fetched}")
    
    logging.info("Script execution completed.")
