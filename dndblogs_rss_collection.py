import requests
import os
import json
import logging
import io
import time
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
    logging.info(f"Fetching data from tracker gist: {gist_id}")
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    gist_url = f"https://api.github.com/gists/{GIST_ID_TRACKER}"
    response = requests.get(gist_url, headers=headers)
    if response.status_code == 403:
        logging.error(f"Error response in fetch_gist_data: {response.text}")
    response.raise_for_status()
    gist_content = list(response.json()["files"].values())[0]["content"]
    return json.loads(gist_content)

def fetch_last_fetched_date():
    data = fetch_gist_data(GIST_URL_TRACKER, GIST_TOKEN)
    return dateutil.parser.parse(data[0]['last_fetched'])

def update_last_fetched_date(new_date):
    data = fetch_gist_data(GIST_URL_TRACKER)
    data[0]['last_fetched'] = new_date.isoformat()
    
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    gist_url = f"https://api.github.com/gists/{GIST_ID_TRACKER}"
    updated_content = json.dumps(data, indent=4)
    requests_data = {
        "files": {
            FILE_NAME_TRACKER: {
                "content": updated_content
            }
        }
    }
    response = requests.patch(gist_url, headers=headers, json=requests_data)
    response.raise_for_status()

def fetch_rss_articles_since_date_xml(rss_url, since_date, blog_name):
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
                "blog_name": blog_name,
                "url": item.find("link").text,
                "title": item.find("title").text,
                "date_published": pub_date.strftime("%Y-%m-%d")                
            })
    return articles
    
def update_gist(gist_id, data, filename, token):
    """Update the specified gist with the provided data."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    gist_url = f"https://api.github.com/gists/{gist_id}"
    updated_content = json.dumps(data, indent=4)
    payload = {
        "files": {
            filename: {
                "content": updated_content
            }
        }
    }
    response = requests.patch(gist_url, headers=headers, json=payload)
    response.raise_for_status()
    return response.status_code

if __name__ == "__main__":
    logging.info("Script started.")
    
    # 1. Fetch Data Once
    tracker_data = fetch_gist_data(GIST_ID_TRACKER, GIST_TOKEN)
    last_fetched = fetch_last_fetched_date()
    details_data = fetch_gist_data(GIST_ID_DETAILS, GIST_TOKEN)

    # Ensure details_data is a list; if not, reset it to an empty list
    if not isinstance(details_data, list):
        logging.warning("Details gist data format unexpected; resetting to an empty list.")
        details_data = []
    
    for blog in tracker_data["blogs"]:
        blog_name = blog["blog_name"]
        rss_url = blog["rss_url"]
        
        logging.info(f"Processing articles for blog: {blog_name} since {last_fetched}")
        
        # 2. Process RSS Feeds
        try:
            new_articles = fetch_rss_articles_since_date_xml(rss_url, last_fetched, blog_name)
        
            # If there are new articles, process them
            if new_articles:
                for article in new_articles:
                    # Append to in-memory details data
                    new_article = {
                        "blog_name": article["blog_name"],
                        "url": article["url"],
                        "title": article["title"],
                        "date_published": article["date_published"],
                        "posted": False
                    }
                    details_data.append(new_article)
            else:
                logging.info(f"No new articles found for blog: {blog_name} since {last_fetched}")
                
        except Exception as e:
            logging.error(f"Error processing articles for blog: {blog_name}. Error: {e}")
    
    # 3. Update Gists Once
    update_gist(GIST_ID_DETAILS, details_data, FILE_NAME_DETAILS, GIST_TOKEN)
    
    # 4. Update the last fetched date to now
    update_last_fetched_date(datetime.now().strftime('%Y-%m-%d'))

    logging.info("Script execution completed.")
