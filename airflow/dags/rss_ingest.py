from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import feedparser
from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer
from app.search.opensearch_client import SearchClient
from dateutil import parser 
import json
import os

# --- Step 1: Define the Functions FIRST to avoid NameErrors ---

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
        print(f"Successfully created {index_name} with HNSW vector support.")
    else:
        print(f"Index {index_name} already exists. Skipping creation.")

def ingest_rss_logic():
    """Scrapes The Economist and stores vectorized content."""
    feeds = ['https://www.economist.com/the-world-this-week/rss.xml']
    client = OpenSearch([{'host': 'opensearch', 'port': 9200}])
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    for url in feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            # --- FIX: Standardize the date ---
            try:
                # Converts "Tue, 05 May..." to "2026-05-05T09:13:54"
                raw_date = entry.get('published', '')
                clean_date = parser.parse(raw_date).isoformat()
            except Exception:
                clean_date = datetime.now().isoformat()
            
            doc = {
                'title': entry.title,
                'link': entry.link,
                'description': entry.description,
                'publish_date': clean_date, # Now in ISO format
                'vector': model.encode(entry.description).tolist()
            }
            client.index(index='news_index', body=doc)
    print("Ingestion complete.")

# --- Step 2: Define the Unified DAG ---

with DAG(
    'contrarian_unified_pipeline',
    start_date=datetime(2026, 1, 1),
    schedule_interval='@daily',
    catchup=False
) as dag:

    # Task 1: Initialize Schema
    setup_index_task = PythonOperator(
        task_id='setup_opensearch_index',
        python_callable=setup_opensearch_index
    )

    # Task 2: Fetch and Vectorize
    retrieve_data_task = PythonOperator(
        task_id='fetch_and_index_rss',
        python_callable=ingest_rss_logic
    )

    # Sequence: Setup Index -> Then Ingest Data
    setup_index_task >> retrieve_data_task