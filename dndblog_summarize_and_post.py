import requests
import os
import json
import logging
import io
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from transformers import BartForConditionalGeneration, BartTokenizer
from datetime import datetime
import re
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
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

# Initialize BART model and tokenizer
MODEL_NAME = "facebook/bart-large-cnn"
MODEL = BartForConditionalGeneration.from_pretrained(MODEL_NAME)
TOKENIZER = BartTokenizer.from_pretrained(MODEL_NAME)

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

def mark_article_as_posted(url, gist_id, token):
    current_data = fetch_gist_data(gist_id, token)
    for article in current_data:
        if article["url"] == url:
            article["posted"] = True
            break
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

# Functions related to summarizing and posting articles
def summarize_and_post_article(details_gist_id, tracker_gist_id, token, squabblr_token):
    article = fetch_oldest_unposted_article(details_gist_id, token)
    if not article:
        return "No unposted articles found."
    summary = get_summary(article["url"])
    title = article["title"]
    content = f"{summary}\n\n[Read more]({article['url']})"
    post_reply(title, content, squabblr_token)
    mark_article_as_posted(article["url"], details_gist_id, token)
    return f"Article '{title}' summarized and posted successfully."
        
def split_into_sentences(text):
    # Use regular expression to split sentences by common punctuation used at the end of sentences
    return re.split(r'(?<=[.!?])\s+', text)
    
def extract_content_with_bs(url):
    """
    Extracts main content of an article using BeautifulSoup
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # Log the initiation of the request
    logging.info(f"Initiating request to URL: {url}")
    
    response = requests.get(url, headers=headers)
    
    # Log the response status code
    logging.info(f"Received response with status code: {response.status_code}")

    # Start parsing with BeautifulSoup
    logging.info(f"Starting content extraction for URL: {url}")
    soup = BeautifulSoup(response.text, 'html.parser')

    # Remove header and footer content
    for header in soup.find_all('header'):
        header.decompose()
    for footer in soup.find_all('footer'):
        footer.decompose()

    # Extract title
    title_tag = soup.find('title')
    title = title_tag.text if title_tag else ''
    
    # Log if the title was found or not
    if title:
        logging.info(f"Title found for URL: {url} - '{title}'")
    else:
        logging.warning(f"No title found for URL: {url}")

    # Extract meta description
    meta_description = ""
    meta_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if meta_tag:
        meta_description = meta_tag.attrs.get("content", "")

    # Extract main content based on common tags used for main article content
    content_tags = ['p']
    content_elements = soup.find_all(content_tags)
    
    # Extract text from each content element and filter out short or irrelevant content
    content = [el.text for el in content_elements if len(el.text.split()) > 5 and title not in el.text]
    
    # Log the number of paragraphs/content tags found
    logging.info(f"Found {len(content)} paragraphs/content tags for URL: {url}")

    # Join content and return
    full_content = '\n'.join(content)

    logging.info(f"Found {len(content)} paragraphs/content tags for URL: {url}")
    logging.info(f"Content snippet for URL: {url} - '{full_content[:100]}...'")

    return full_content, title, meta_description

def split_into_chunks(text, chunk_size=5):
    """
    Split the content into chunks of given size.
    """
    paragraphs = text.split('\n')
    chunks = [paragraphs[i:i+chunk_size] for i in range(0, len(paragraphs), chunk_size)]
    return ['\n'.join(chunk) for chunk in chunks]

def generate_summary(text, max_length=150):
    # Ensure the MODEL and TOKENIZER are available
    global MODEL, TOKENIZER
    
    inputs = TOKENIZER.encode("summarize: " + text, return_tensors="pt", max_length=1024, truncation=True)
    outputs = MODEL.generate(inputs, max_length=max_length, min_length=50, length_penalty=5.0, num_beams=2, early_stopping=True)
    summary = TOKENIZER.decode(outputs[0], skip_special_tokens=True)
    
    return summary

def generate_comprehensive_summary(content):
    """
    Generate a summary by splitting the content into chunks and summarizing each chunk.
    """
    chunks = split_into_chunks(content)
    summaries = [generate_summary(chunk) for chunk in chunks]
    
    # Combine the summaries
    combined_summary = ' '.join(summaries)

    # Limit the combined summary to a maximum of 7 sentences
    sentences = split_into_sentences(combined_summary)
    if len(sentences) > 7:
        combined_summary = ' '.join(sentences[:7])

    # Post-process the summary to remove irrelevant lines
    cleaned_summary = post_process_summary(combined_summary)

    return cleaned_summary

def post_process_summary(summary):
    """
    Post-process the summary to remove any irrelevant or out-of-context lines.
    """
    lines = summary.split('. ')
    cleaned_lines = [line for line in lines if not line.startswith("summarize:")]
    
    return '. '.join(cleaned_lines)


def get_summary(article):
    try:
        logging.info(f"Starting the summary generation for article content")

        if not article or len(article.strip()) == 0:
            logging.error(f"No valid content provided.")
            return None

        # Generate a comprehensive summary by handling the text in chunks.
        summary = generate_comprehensive_summary(article)
        logging.info(f"Summary generated.")

        # Extract main points
        main_points = get_main_points(article)
        
        # Remove points that are very similar to the summary
        main_points = [point for point in main_points if point not in summary]
    
        return summary, main_points

    except Exception as e:
        logging.error(f"Error in generating summary. Error: {e}")
        return None, None

def get_main_points(text, num_points=5):
    """
    Extracts the main points from the given text using TF-IDF ranking.
    """
    # Tokenize the article into sentences
    sentences = split_into_sentences(text)
    
    # Use TF-IDF to rank sentences with tweaked parameters
    tfidf_vectorizer = TfidfVectorizer(stop_words='english', max_df=0.9, min_df=3, ngram_range=(1,2))
    tfidf_matrix = tfidf_vectorizer.fit_transform(sentences)
    
    # Sum the TF-IDF scores for each sentence to get an overall score for the sentence
    sentence_scores = tfidf_matrix.sum(axis=1).tolist()
    
    # Rank sentences based on their scores
    ranked_sentences = [sentences[idx] for idx, score in sorted(enumerate(sentence_scores), key=lambda x: x[1], reverse=True)]
    
    # Extract top n sentences as main points
    main_points = ranked_sentences[:num_points]

    return main_points

def post_article(post_id, content):
    headers = {
        'authorization': 'Bearer ' + SQUABBLES_TOKEN
    }
    
    resp = requests.post('https://squabblr.co/api/new-post', data={
        "community_name": "test",
        "title": title,
        "content": content
    }, headers=headers)

    return resp.json()
    
    if resp.status_code in [200, 201]:
        logging.info(f"Successfully posted a reply for post ID: {post_id}")
    else:
        logging.warning(f"Failed to post a reply for post ID: {post_id}.")

    # Log the response status and content
    logging.info(f"Response status from Squabblr API when posting reply: {resp.status_code}")
    logging.info(f"Response content from Squabblr API when posting reply: {resp.text}")
    
    return resp.json()

if __name__ == "__main__":
    main()
