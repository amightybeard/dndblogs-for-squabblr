import os
import json
import requests
import logging

logging.basicConfig(level=logging.INFO)

# Constants
SQUABBLR_TOKEN = os.environ.get('SQUABBLR_TOKEN')
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
    try:
        logging.info("Fetching articles data...")
        response = requests.get(GIST_URL_DETAILS)
        if response.status_code != 200:
            logging.error(f"Error fetching articles data: {response.status_code}, {response.text}")
            exit(1)

        articles = response.json()
        logging.info("Article data fetched successfully.")

        # Find the first article that hasn't been posted
        for article in articles:
            if not article["posted"]:
                # Prepare title and content
                post_title = f"[{article['blog_name']}] {article['title']}"
                post_description = article.get("description", "").replace("\n", " ").replace("\r", "").strip()  # Cleaning up newlines and spaces
                post_content = f"""By [{article['blog_name']}]({article['url']})

-----

{post_description}

-----
 
I'm a bot. Post feedback, blog inclusion requests, and suggestions to /s/ModBot. [Read the announcement post](https://squabblr.co/u/modbot/post/G8wA45APxz)."""

                # Post to Squabblr.co
                post_response = post_to_squabblr(post_title, post_content)
                if 'error' in post_response:
                    logging.error(f"Error posting article: {post_response['error']}")
                    exit(1)
                logging.info(f"Article '{post_title}' posted successfully.")

                # Update the article's "posted" status
                article["posted"] = True

                logging.info(f"Updating nflblogs-article-details.json to mark '{article['title']}' as posted...")
                # Update nflblogs-article-details.json gist with the updated article
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
                if response.status_code != 200:
                    logging.error(f"Error updating nflblogs-article-details.json: {response.status_code}, {response.text}")
                    exit(1)
                logging.info(f"'{article['title']}' marked as posted successfully.")
                
                break  # Exit the loop after posting one article
    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")

logging.info("Bot completed.")

if __name__ == "__main__":
    main()
