import requests
import os
import json
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Constants
SQUABBLR_TOKEN = os.environ.get('SQUABBLR_TOKEN')
GIST_TOKEN =  os.environ.get('DNDBLOGS_GIST_TOKEN')
GIST_ID_DETAILS = os.environ.get('DNDBLOGS_GIST_DETAILS')
FILE_NAME_DETAILS = 'dndblogs-article-details.json'
GIST_URL_DETAILS = f"https://gist.githubusercontent.com/amightybeard/{GIST_ID_DETAILS}/raw/{FILE_NAME_DETAILS}"
DATE_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'

def post_to_squabblr(title, content):
    headers = {
        'authorization': 'Bearer ' + SQUABBLR_TOKEN
    }
    response = requests.post('https://squabblr.co/api/new-post', data={
        "community_name": "test",
        "title": title,
        "content": content
    }, headers=headers)
    
    response.raise_for_status()
    return response.json()

def fetch_first_unposted_article():
    data = requests.get(GIST_URL_DETAILS, GIST_TOKEN)
    for article in data:
        if not article['posted']:
            return [article]
    return []

def update_posted_status_for_article(article):
    articles = fetch_first_unposted_article()  # Fetch all articles again
    if articles:  # Check if the list is not empty
        articles[0]['posted'] = True  # Update the first (and only) article in the list
        update_article_details_gist(articles[0])
        
    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    gist_url = f"https://api.github.com/gists/{GIST_ID_DETAILS}"
    updated_content = json.dumps(articles, indent=4)
    data = {
        "files": {
            FILE_NAME_DETAILS: {
                "content": updated_content
            }
        }
    }
    response = requests.patch(gist_url, headers=headers, json=data)
    response.raise_for_status()
    return response.status_code

if __name__ == "__main__":
    logging.info("Script started.")
    
    # Fetch first unposted article
    article = fetch_first_unposted_article()
    if article:
        title = article['title']
        content = f"{article['url']}\n\n*Written by: {article['blog_name']} on {article['date_published']}.*\n\n-----\n\nI'm a bot. To send feedback or suggestions, post on /s/ModBot."
        post_to_squabblr(title, content)
        update_posted_status_for_article(article)
        logging.info(f"Article '{title}' posted and status updated.")
    else:
        logging.info("No unposted articles found.")
    
    logging.info("Script execution completed.")