# politics_rss_collection.py

import requests
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import urlparse, urlunparse
from datetime import datetime

# Constants
GIST_TOKEN = os.environ.get('POL_GIST_TOKEN')
GIST_ID_DETAILS = '6c90a5d9642610efdbf83840dfc0fb76'
FILE_NAME_DETAILS = 'politics-article-details.json'

def get_rss_feed(url):
    response = requests.get(url)
    return response.text

def parse_votes_description(description):
    """
    Parses the description for vote results which are in the format "Passed X/Y".
    """
    if 'Vote:' in description:
        vote_result = description.split("Vote:")[1].strip()
        return vote_result
    return None

def parse_activity_description(description):
    """
    Parses the description for activity information which includes the last action and next step.
    """
    last_action = None
    next_step = None
    if 'Last Action:' in description and 'Explanation:' in description:
        parts = description.split("Last Action:")
        last_action = parts[1].split("Explanation:")[0].strip()
        next_step = parts[1].split("Explanation:")[1].strip()
    return last_action, next_step

def parse_rss_item(item, feed_type):
    title = item.find('title').text
    link = item.find('link').text
    description = item.find('description').text

    # Extract and convert pubDate
    pub_date_str = item.find('pubDate').text
    pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %z')
    
    # Parse the URL to remove the query parameters
    parsed_url = urlparse(link)
    clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
    
    # For bill_text, append /text to the clean URL
    bill_text = clean_url + '/text'

    # Scrape additional info based on the link and feed type
    bill_overview, bill_summary = scrape_additional_info(link, feed_type)

    # Initialize the article details dictionary
    article_details = {
        'bill_title': title,
        'bill_link': link,
        'bill_description': description,
        'bill_overview': bill_overview,
        'bill_text': bill_text,
        'bill_summary': bill_summary,
        'pub_date': pub_date.strftime('%Y-%m-%d %H:%M:%S'),  # Formatting date for JSON serialization
        'posted': False,
        'type': feed_type
    }
    
    # New parsing logic for 'Votes' and 'Activity' types
    if feed_type == 'Votes':
        vote_result = parse_votes_description(description)
        if vote_result:
            article_details['vote_result'] = vote_result
    elif feed_type == 'Activity':
        last_action, next_step = parse_activity_description(description)
        if last_action:
            article_details['last_action'] = last_action
        if next_step:
            article_details['next_step'] = next_step

    return article_details

def process_all_rss_items(rss_items, feed_type):
    all_items = [parse_rss_item(item, feed_type) for item in rss_items]
    return all_items

# In your main script or main function
all_items_from_all_feeds = []

# Loop through all RSS feeds and aggregate all items
for feed_url, feed_type in rss_urls:
    rss_items = fetch_rss_items(feed_url)  # Assume you have a function that fetches and returns all items from an RSS feed
    all_items = process_all_rss_items(rss_items, feed_type)
    all_items_from_all_feeds.extend(all_items)

# Sort all items based on pub_date
sorted_items = sorted(all_items_from_all_feeds, key=lambda x: x['pub_date'], reverse=True)

# Convert datetime back to string for JSON serialization
for item in sorted_items:
    item['pub_date'] = item['pub_date'].strftime('%a, %d %b %Y %H:%M:%S %z')

for item in sorted_items:
    item['pub_date'] = item['pub_date'].strftime('%a, %d %b %Y %H:%M:%S %z')
    
def scrape_additional_info(link, feed_type):
    parsed_url = urlparse(link)
    clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
    
    response = requests.get(link)
    soup = BeautifulSoup(response.text, 'html.parser')
    content_div = soup.find(id='content')
    bill_overview = content_div.find(lambda tag: tag.name == 'p' and tag.parent == content_div)
    bill_overview = bill_overview.text if bill_overview else ''
    bill_summary = ''
    if feed_type == 'Activity':
        summary_link = clean_url + '/summary'
        summary_response = requests.get(summary_link)
        summary_soup = BeautifulSoup(summary_response.text, 'html.parser')
        summary_div = summary_soup.find(id='libraryofcongress')
        
        if summary_div:
            bill_summary = " ".join([p.text for p in summary_div.find_all('p')])  # Concatenating all paragraphs
        else:
            print(f"Warning: Missing or malformed summary for {link}. Proceeding with empty summary.")
            bill_summary = ''
    elif feed_type == 'Votes':
        vote_explainer_div = soup.find(id='vote_explainer')
        vote_explainer_link = "https://www.govtrack.us" + vote_explainer_div.a['href'] if vote_explainer_div and vote_explainer_div.a else ''
        if vote_explainer_div and vote_explainer_div.a and 'href' in vote_explainer_div.a.attrs:
            vote_explainer_link = "https://www.govtrack.us" + vote_explainer_div.a['href']
        else:
            print(f"Warning: Missing or malformed vote explainer link for {link}. Proceeding with empty explainer link.")
            vote_explainer_link = ''
            
        explainer_response = requests.get(vote_explainer_link)
        explainer_soup = BeautifulSoup(explainer_response.text, 'html.parser')
        content_div = explainer_soup.find(id='content')
        bill_overview = content_div.find('p').text if content_div else ''
        bill_text_link = vote_explainer_link.replace('?utm_campaign=govtrack_feed&amp;utm_source=govtrack/feed&amp;utm_medium=rss', '/text')
    return bill_overview, bill_summary  # Removed bill_text_link

import requests

def write_to_json(data, file_name):
    """
    Write the given data to a Gist file.

    Parameters:
    data (dict): The data to write to the file.
    file_name (str): The name of the file to write to.

    Returns:
    None
    """
    
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    payload = {
        "files": {
            file_name: {
                "content": json.dumps(data, indent=4, ensure_ascii=False)
            }
        }
    }
    
    response = requests.patch(f"https://api.github.com/gists/{GIST_ID_DETAILS}", headers=headers, json=payload)
    
    if response.status_code == 200:
        print(f"Successfully updated {file_name} in gist {GIST_ID_DETAILS}")
    else:
        print(f"Failed to update gist. Status code: {response.status_code}, Response: {response.text}")


def main():
    # URLs of the RSS feeds
    rss_urls = [
        ('https://www.govtrack.us/events/events.rss?list_id=2xtKwzEbrPGqdftV', 'Activity'),
        # ('https://www.govtrack.us/events/events.rss?list_id=bIEEeNizAdvQ12hc', 'Votes'),
        ('https://www.govtrack.us/events/events.rss?list_id=jjfjQNLQe3meewpG', 'New')
    ]
    all_items = []
    for url, feed_type in rss_urls:
        rss_content = get_rss_feed(url)
        items = parse_rss(rss_content, feed_type)
        all_items.extend(items)
    write_to_json(all_items, FILE_NAME_DETAILS)

if __name__ == "__main__":
    main()
