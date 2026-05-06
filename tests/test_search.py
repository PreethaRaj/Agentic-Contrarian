import pytest
from app.search.opensearch_client import SearchClient

def test_search_connection():
    try:
        client = SearchClient()
        # Ping the cluster
        assert client.client.ping() is True
    except Exception as e:
        pytest.fail(f"Connection to OpenSearch failed: {e}")