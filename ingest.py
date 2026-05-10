# ingest.py  — run directly: python ingest.py
# Standalone version of the RSS ingest logic.
# No Airflow required. Run this from C:\Projects\contrarian-app\ with venv active.

import os
import json
import feedparser
from datetime import datetime
from dateutil import parser as dateparser
from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")

FEEDS = {
    "mainstream": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://www.theguardian.com/world/rss",
    ],
    "opinion": [
        "https://www.economist.com/the-world-this-week/rss.xml",
        "https://foreignpolicy.com/feed/",
    ],
    "trade": [
        "https://techcrunch.com/feed/",
    ],
    "analyst": [
        "https://www.brookings.edu/feed/",
        "https://www.cfr.org/rss.xml",
    ],
    "regional": [
        "https://www.channelnewsasia.com/rss-feeds/8395904",
        "https://feeds.skynews.com/feeds/rss/world.xml",
    ],
}

MAPPING = {
    "mappings": {
        "properties": {
            "title":           {"type": "text"},
            "link":            {"type": "keyword"},
            "description":     {"type": "text"},
            "publish_date":    {"type": "date"},
            "source_name":     {"type": "keyword"},
            "source_category": {"type": "keyword"},
            "vector": {
                "type": "knn_vector",
                "dimension": 384,
                "method": {
                    "name":       "hnsw",
                    "space_type": "cosinesimil",
                    "engine":     "nmslib",
                },
            },
        }
    },
    "settings": {
        "index": {"knn": True}
    },
}


def get_client():
    return OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": 9200}],
        http_auth=("admin", "admin"),
        use_ssl=False,
        verify_certs=False,
    )


def setup_index(client):
    if not client.indices.exists(index="news_index"):
        client.indices.create(index="news_index", body=MAPPING)
        print("[ingest] Created news_index with HNSW mapping.")
    else:
        print("[ingest] news_index already exists.")


def ingest():
    client = get_client()

    # Ping first — clear error if OpenSearch not running
    if not client.ping():
        print("[ingest] ERROR: Cannot reach OpenSearch at "
              f"{OPENSEARCH_HOST}:9200\n"
              "  → Make sure Docker is running: docker compose up -d\n"
              "  → Wait 30s then retry.")
        return

    setup_index(client)
    model = SentenceTransformer("all-MiniLM-L6-v2")
    total = 0

    for category, urls in FEEDS.items():
        for url in urls:
            print(f"[ingest] Fetching [{category}] {url}")
            try:
                feed = feedparser.parse(url)
            except Exception as e:
                print(f"  SKIP — parse error: {e}")
                continue

            for entry in feed.entries:
                description = (
                    getattr(entry, "description", "")
                    or getattr(entry, "summary", "")
                    or ""
                )
                if not description.strip():
                    continue

                try:
                    raw_date = entry.get("published", "")
                    clean_date = (
                        dateparser.parse(raw_date).isoformat()
                        if raw_date else datetime.now().isoformat()
                    )
                except Exception:
                    clean_date = datetime.now().isoformat()

                doc = {
                    "title":           entry.get("title", ""),
                    "link":            entry.get("link", ""),
                    "description":     description,
                    "publish_date":    clean_date,
                    "source_name":     feed.feed.get("title", url),
                    "source_category": category,
                    "vector":          model.encode(description).tolist(),
                }
                try:
                    client.index(index="news_index", body=doc)
                    total += 1
                except Exception as e:
                    print(f"  Index error: {e}")

    print(f"\n[ingest] Done. {total} articles indexed into news_index.")
    print("[ingest] You can now run queries in the dashboard.")


if __name__ == "__main__":
    ingest()
