# politics_rss_collection.py

import requests
from bs4 import BeautifulSoup
import json
import os

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
    bill_overview, bill_text, bill_summary = scrape_additional_info(link, feed_type)
    return {
        'bill_title': title,
        'bill_link': link,
        'bill_description': description,
        'bill_overview': bill_overview,
        'bill_text': bill_text,
        'bill_summary': bill_summary,
        'posted': False,
        'type': feed_type
    }

def scrape_additional_info(link, feed_type):
    response = requests.get(link)
    soup = BeautifulSoup(response.text, 'html.parser')
    content_div = soup.find(id='content')
    bill_overview = content_div.find('p').text if content_div else ''
    bill_text_link = link.replace('?utm_campaign=govtrack_feed&amp;utm_source=govtrack/feed&amp;utm_medium=rss', '/text')
    bill_summary = ''
    if feed_type == 'Activity':
        summary_link = link.replace('?utm_campaign=govtrack_feed&amp;utm_source=govtrack/feed&amp;utm_medium=rss', '/summary')
        summary_response = requests.get(summary_link)
        summary_soup = BeautifulSoup(summary_response.text, 'html.parser')
        summary_div = summary_soup.find(id='libraryofcongress')
        bill_summary = summary_div.text if summary_div else ''
    elif feed_type == 'Votes':
        vote_explainer_div = soup.find(id='vote_explainer')
        vote_explainer_link = vote_explainer_div.find('a')['href'] if vote_explainer_div else ''
        explainer_response = requests.get(vote_explainer_link)
        explainer_soup = BeautifulSoup(explainer_response.text, 'html.parser')
        content_div = explainer_soup.find(id='content')
        bill_overview = content_div.find('p').text if content_div else ''
        bill_text_link = vote_explainer_link.replace('?utm_campaign=govtrack_feed&amp;utm_source=govtrack/feed&amp;utm_medium=rss', '/text')
    return bill_overview, bill_text_link, bill_summary

def write_to_json(data, file_name):
    with open(file_name, 'w', encoding='utf-8') as outfile:
        json.dump(data, outfile, ensure_ascii=False, indent=4)

def main():
    # URLs of the RSS feeds
    rss_urls = [
        ('https://www.govtrack.us/events/events.rss?list_id=2xtKwzEbrPGqdftV', 'Activity'),
        ('https://www.govtrack.us/events/events.rss?list_id=bIEEeNizAdvQ12hc', 'Votes'),
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