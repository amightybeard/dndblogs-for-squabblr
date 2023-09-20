import os
import json
import requests
import logging

logging.basicConfig(level=logging.INFO)

# Constants
SQUABBLR_TOKEN = os.environ.get('NFLBLOGS_SQUABBLR_TOKEN')
GIST_TOKEN = os.environ.get('NFLBLOGS_GIST_TOKEN')
GIST_ID_DETAILS = os.environ.get('NFLBLOGS_GIST_DETAILS')
FILE_NAME_DETAILS = 'nflblogs-article-details.json'
GIST_URL_DETAILS = f"https://gist.githubusercontent.com/amightybeard/{GIST_ID_DETAILS}/raw/{FILE_NAME_DETAILS}"

def post_to_squabblr(title, content):
    logging.info(f"Posting article '{title}' to Squabblr.co...")
    headers = {
        'authorization': 'Bearer ' + SQUABBLR_TOKEN
    }
    response = requests.post('https://squabblr.co/api/new-post', data={
        "community_name": "nfl",
        "title": title,
        "content": content
    }, headers=headers)
    logging.info(f"Article '{title}' posted successfully.")
    return response.json()

def main():
    logging.info("Fetching articles data...")
    response = requests.get(GIST_URL_DETAILS)
    articles = response.json()
    logging.info("Article data fetched successfully.")

    # Find the first article that hasn't been posted
    for article in articles:
        if not article["posted"]:
            # Prepare title and content
            post_title = f"[{article['blog_name']}] {article['title']}"
            post_content = f"Check out [{article['title']}]({article['url']}) by {article['blog_name']}\n\n-----\n\nI'm a bot. Post feedback, blog inclusion requests, and suggestions to /s/ModBot."

            # Post to Squabblr.co
            post_to_squabblr(post_title, post_content)

            # Update the article's "posted" status
            article["posted"] = True

            logging.info(f"Updating dndblogs-article-details.json to mark '{article['title']}' as posted...")
            # Update dndblogs-article-details.json gist with the updated article
            headers = {
                "Authorization": f"token {GIST_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            payload = {
                "files": {
                    FILE_NAME_DETAILS: {
                        "content": json.dumps(articles, indent=4)
                    }
                }
            }
            response = requests.patch(f"https://api.github.com/gists/{GIST_ID_DETAILS}", headers=headers, json=payload)
            logging.info(f"'{article['title']}' marked as posted successfully.")
            
            break  # Exit the loop after posting one article

if __name__ == "__main__":
    main()
