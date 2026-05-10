from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import feedparser
from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer
from app.search.opensearch_client import SearchClient
from dateutil import parser as dateparser
import json
import os

# --- EXPANDED FEED LIST covering multiple source categories ---
# Trade-off: more feeds = longer ingest time. Adjust schedule_interval if needed.
FEEDS = {
    # Mainstream / wire
    "mainstream": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://www.theguardian.com/world/rss",
    ],
    # Opinion / editorial
    "opinion": [
        "https://www.economist.com/the-world-this-week/rss.xml",
        "https://feeds.feedburner.com/ForeignAffairs",
        "https://foreignpolicy.com/feed/",
    ],
    # Trade / industry
    "trade": [
        "https://techcrunch.com/feed/",
        "https://www.ft.com/rss/home/uk",          # FT (may require auth — skip gracefully)
        "https://www.bloomberg.com/feeds/podcasts/etf.xml",  # public Bloomberg podcast feed
    ],
    # Analyst / think-tank
    "analyst": [
        "https://www.brookings.edu/feed/",
        "https://www.cfr.org/rss.xml",
    ],
    # Regional / local aggregator
    "regional": [
        "https://www.channelnewsasia.com/rss-feeds/8395904",  # Asia regional
        "https://feeds.skynews.com/feeds/rss/world.xml",
    ],
}

def setup_opensearch_index():
    """Ensures the index exists with the correct HNSW mappings."""
    client = SearchClient()
    # Path relative to the container's dags folder
    mapping_path = '/opt/airflow/dags/mappings.json' 
    
    if not os.path.exists(mapping_path):
        raise FileNotFoundError(f"Missing mappings.json at {mapping_path}")

    with open(mapping_path, "r") as f:
        mapping = json.load(f)

    index_name = "news_index"
    if not client.client.indices.exists(index=index_name):
        client.client.indices.create(index=index_name, body=mapping)
        print(f"Created {index_name} with HNSW vector support.")
    else:
        print(f"Index {index_name} already exists. Skipping creation.")


def ingest_rss_logic():
    """Scrapes curated multi-category feeds and stores vectorized content."""
    os_client = OpenSearch([{'host': 'opensearch', 'port': 9200}])
    model = SentenceTransformer('all-MiniLM-L6-v2')
    total_indexed = 0

    for category, feed_urls in FEEDS.items():
        for url in feed_urls:
            try:
                feed = feedparser.parse(url)
            except Exception as e:
                print(f"[ingest] Failed to parse feed {url}: {e}")
                continue

            for entry in feed.entries:
                try:
                    raw_date = entry.get('published', '')
                    clean_date = dateparser.parse(raw_date).isoformat() if raw_date else datetime.now().isoformat()
                except Exception:
                    clean_date = datetime.now().isoformat()

                description = getattr(entry, 'description', '') or getattr(entry, 'summary', '') or ''
                if not description.strip():
                    continue

                doc = {
                    'title':           entry.get('title', ''),
                    'link':            entry.get('link', ''),
                    'description':     description,
                    'publish_date':    clean_date,
                    'source_name':     feed.feed.get('title', url),  # NEW: for reranker
                    'source_category': category,                      # NEW: for reranker
                    'vector':          model.encode(description).tolist(),
                }
                try:
                    os_client.index(index='news_index', body=doc)
                    total_indexed += 1
                except Exception as e:
                    print(f"[ingest] Index error for {entry.get('link','?')}: {e}")

    print(f"[ingest] Complete. {total_indexed} docs indexed across {sum(len(v) for v in FEEDS.values())} feeds.")


with DAG(
    'contrarian_unified_pipeline',
    start_date=datetime(2026, 1, 1),
    schedule_interval='@daily',
    catchup=False,
) as dag:

    setup_index_task = PythonOperator(
        task_id='setup_opensearch_index',
        python_callable=setup_opensearch_index,
    )

    retrieve_data_task = PythonOperator(
        task_id='fetch_and_index_rss',
        python_callable=ingest_rss_logic,
    )

    setup_index_task >> retrieve_data_task
