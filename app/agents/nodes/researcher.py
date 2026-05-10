from app.agents.state import AgentState
import time
from app.agents.state import AgentState
from app.config import (
    MAX_RESULTS_TOTAL,
    SOURCE_CATEGORIES,
    EXTRA_VARIANTS,
)


def expand_queries(base_query: str) -> list[tuple[str, str]]:
    variants: list[tuple[str, str]] = []

    # Primary category suffixes
    for category, suffix in SOURCE_CATEGORIES:
        q = f"{base_query} {suffix}".strip()
        variants.append((q, category))

    # Extra framing templates
    for template, category in EXTRA_VARIANTS:
        q = template.format(q=base_query)
        variants.append((q, category))

    return variants


class ResearcherNode:
    def __init__(self, search_service):
        self.search_service = search_service

    def __call__(self, state: AgentState):
        base_query = state.get("query", "")
        variants = expand_queries(base_query)
        per_variant_limit = max(3, MAX_RESULTS_TOTAL // len(variants))

        seen_urls: set = set()
        evidence_pool: list = []

        for variant_query, category in variants:
            if len(evidence_pool) >= MAX_RESULTS_TOTAL:
                break
            try:
                results = self.search_service.search(
                    variant_query, page_size=per_variant_limit
                )
            except Exception as e:
                print(f"[ResearcherNode] Error on variant '{variant_query}': {e}")
                results = []

            for doc in results:
                url = doc.get("url", "") or ""
                title = doc.get("title", "") or ""
                # Dedup key: prefer URL; fall back to title to catch blank-URL dupes
                dedup_key = url if url else title
                if not dedup_key or dedup_key in seen_urls:
                    continue
                seen_urls.add(dedup_key)

                content = doc.get("description") or doc.get("content") or ""
                if not content.strip():
                    continue

                evidence_pool.append({
                    "source_id": f"NEWS_{len(evidence_pool) + 1}",
                    "content":   content,
                    "url":       url,
                    "source_category": category,
                    "stance":          "unclassified",
                    "metadata": {
                        "title":       doc.get("title", ""),
                        "published_at": doc.get("publishedAt", ""),
                        "source_name": (
                            doc.get("source", {}).get("name", "")
                            if isinstance(doc.get("source"), dict)
                            else str(doc.get("source", ""))
                        ),
                    },
                })

            time.sleep(0.2)  # Rate-limit guard between variant calls

        print(
            f"[ResearcherNode] {len(evidence_pool)} unique articles "
            f"from {len(variants)} variants."
        )
        return {"evidence_pool": evidence_pool}
