# app/search/opensearch_client.py
import os
from opensearchpy import OpenSearch

class SearchClient:
    def __init__(self):
        # This checks the environment variable we set in docker-compose
        # If not found, it falls back to localhost for your IDE runs
        host = os.getenv('OPENSEARCH_HOST', 'localhost') 
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': 9200}],
            http_auth=('admin', 'admin'), # Default OpenSearch creds
            use_ssl=False,
            verify_certs=False
        )