# politics_rss_collection.py

import requests
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import urlparse, urlunparse

# Constants
GIST_TOKEN = os.environ.get('POL_GIST_TOKEN')
GIST_ID_DETAILS = '6c90a5d9642610efdbf83840dfc0fb76'
FILE_NAME_DETAILS = 'politics-article-details.json'

def get_rss_feed(url):
    response = requests.get(url)
    return response.text

def parse_rss(xml_content, feed_type):
    soup = BeautifulSoup(xml_content, 'xml')
    items = soup.find_all('item')
    parsed_items = []
    for item in items:
        parsed = parse_rss_item(item, feed_type)
        parsed_items.append(parsed)
    return parsed_items

def parse_rss_item(item, feed_type):
    title = item.find('title').text
    link = item.find('link').text
    description = item.find('description').text
    
    # Parse the URL to remove the query parameters
    parsed_url = urlparse(item.find('link').text)
    clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
    
    # For bill_text, append /text to the clean URL
    bill_text = clean_url + '/text'

    # Log the details of the item being processed
    print(f"Processing: {title} at link: {link}")
    
    bill_overview, bill_summary = scrape_additional_info(link, feed_type)  # Changed here
    
    return {
        'bill_title': title,
        'bill_link': link,
        'bill_description': description,
        'bill_overview': bill_overview,
        'bill_text': bill_text,  # This will now retain the cleaned URL
        'bill_summary': bill_summary,
        'posted': False,
        'type': feed_type
    }

def scrape_additional_info(link, feed_type):
    def scrape_additional_info(link, feed_type):
    response = requests.get(link)
    print(response)
    soup = BeautifulSoup(response.text, 'html.parser')
    content_div = soup.find(id='content')
    bill_overview = content_div.find(lambda tag: tag.name == 'p' and tag.parent == content_div)
    bill_overview = bill_overview.text if bill_overview else ''
    bill_summary = ''
    if feed_type == 'Activity':
        summary_link = link.replace('?utm_campaign=govtrack_feed&amp;utm_source=govtrack/feed&amp;utm_medium=rss', '/summary')
        summary_response = requests.get(summary_link)
        summary_soup = BeautifulSoup(summary_response.text, 'html.parser')
        summary_div = summary_soup.find(id='libraryofcongress')
        bill_summary = summary_div.text if summary_div else ''
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
        ('https://www.govtrack.us/events/events.rss?list_id=2xtKwzEbrPGqdftV', 'Activity')
        # ('https://www.govtrack.us/events/events.rss?list_id=bIEEeNizAdvQ12hc', 'Votes'),
        # ('https://www.govtrack.us/events/events.rss?list_id=jjfjQNLQe3meewpG', 'New')
    ]
    all_items = []
    for url, feed_type in rss_urls:
        rss_content = get_rss_feed(url)
        items = parse_rss(rss_content, feed_type)
        all_items.extend(items)
    write_to_json(all_items, FILE_NAME_DETAILS)

if __name__ == "__main__":
    main()
