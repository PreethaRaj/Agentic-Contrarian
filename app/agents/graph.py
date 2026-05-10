from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from app.agents.state import AgentState
from app.agents.nodes.researcher import ResearcherNode
from app.agents.nodes.auditor import AuditorNode
from app.agents.nodes.perspective import PerspectiveAnalystNode
from app.agents.nodes.contrarian import ContrarianNode
from app.search.opensearch_client import SearchClient


class NewsSearchService:
    """OpenSearch adapter. .search(query, page_size) -> list[dict]."""

    def __init__(self):
        self._client = SearchClient()

    def search(self, query: str, page_size: int = 10) -> list:
        try:
            body = {
                "size": page_size,
                "query": {
                    "multi_match": {
                        "query":     query,
                        "fields":             ["title^3", "description^2", "source_name"],
                        "type":               "cross_fields",
                        "operator":           "and",
                        "minimum_should_match": "60%",
                    }
                },
                "sort": [{"publish_date": {"order": "desc"}}],
            }
            resp = self._client.client.search(index="news_index", body=body)
            hits = resp.get("hits", {}).get("hits", [])
            return [
                {
                    "title":       h["_source"].get("title", ""),
                    "description": h["_source"].get("description", ""),
                    "content":     h["_source"].get("description", ""),
                    "url":         h["_source"].get("link", ""),
                    "publishedAt": h["_source"].get("publish_date", ""),
                    "source": {
                        "name":     h["_source"].get("source_name", ""),
                        "category": h["_source"].get("source_category", ""),
                    },
                }
                for h in hits
            ]
        except Exception as e:
            print(f"[NewsSearchService] Query failed: {e}")
            return []


def route_to_contrarian(state: AgentState) -> str:
    """
    Conditional edge after perspective node.
    Skip ContrarianNode entirely when AuditorNode flagged empty/off-topic evidence.
    This is the primary hallucination circuit-breaker.
    """
    if state.get("skip_contrarian", False):
        print("[graph] skip_contrarian=True → routing to END, bypassing ContrarianNode.")
        return END
    return "contrarian"


def create_graph(search_service=None):
    llm = ChatOllama(model="llama3.2", temperature=0.3)
    if search_service is None:
        search_service = NewsSearchService()

    workflow = StateGraph(AgentState)

    workflow.add_node("researcher",  ResearcherNode(search_service))
    workflow.add_node("auditor",     AuditorNode(llm))
    workflow.add_node("perspective", PerspectiveAnalystNode(llm))
    workflow.add_node("contrarian",  ContrarianNode(llm))

    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "auditor")
    workflow.add_edge("auditor",    "perspective")

    # Conditional: bypass ContrarianNode if evidence is empty/off-topic
    workflow.add_conditional_edges(
        "perspective",
        route_to_contrarian,
        {"contrarian": "contrarian", END: END},
    )
    workflow.add_edge("contrarian", END)

    return workflow.compile()


def run_investigation(query: str) -> dict:
    graph = create_graph()
    final_result = graph.invoke({
        "query":                  query,
        "evidence_pool":          [],
        "claims":                 [],
        "missing_perspectives":   [],
        "weak_contrarian_signal": False,
        "skip_contrarian":        False,
        "final_report":           None,
        "report_id":              None,
    })
    print(f"[graph] Done. Evidence: {len(final_result.get('evidence_pool', []))}, "
          f"Claims: {len(final_result.get('claims', []))}, "
          f"Skipped: {final_result.get('skip_contrarian', False)}")
    return final_result
