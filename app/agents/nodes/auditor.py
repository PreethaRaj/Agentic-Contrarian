import json
import re
from app.agents.state import AgentState
from app.config import (
    TOP_K_RERANKED      as TOP_K,
    MIN_CONTRARIAN,
    MIN_RELEVANCE_SCORE,
    STOP_WORDS,
    SUPPORTIVE_SIGNALS,
    SKEPTICAL_SIGNALS,
    CRITICAL_SIGNALS,
    NEUTRAL_SIGNALS,
)


# ── Relevance gate ──────────────────────────────────────────────────────────

def topic_relevance_score(query: str, text: str) -> float:
    """
    Fraction of meaningful query keywords found in article text.
    Returns 0.0–1.0; scores below MIN_RELEVANCE_SCORE drop the article.
    """
    query_tokens = set(re.findall(r'\b\w+\b', query.lower())) - STOP_WORDS
    if not query_tokens:
        return 1.0  # Cannot filter — pass through

    article_tokens = set(re.findall(r'\b\w+\b', (text or "").lower()))
    matches = query_tokens & article_tokens
    return len(matches) / len(query_tokens)


# ── Stance classifier ───────────────────────────────────────────────────────

def classify_stance(text: str) -> str:
    """
    Generic keyword-based stance classification.
    Signals loaded from config so they stay domain-agnostic.
    """
    lower  = (text or "").lower()
    tokens = set(re.findall(r'\b\w+\b', lower))

    has_critical  = bool(tokens & CRITICAL_SIGNALS)
    has_skeptical = bool(tokens & SKEPTICAL_SIGNALS)
    has_support   = bool(tokens & SUPPORTIVE_SIGNALS)
    has_neutral   = bool(tokens & NEUTRAL_SIGNALS)

    if has_critical:
        return "critical"
    if has_skeptical and has_support:
        return "mixed"
    if has_skeptical:
        return "skeptical"
    if has_support:
        return "supportive"
    if has_neutral:
        return "neutral"
    return "neutral"  # default


# ── Reranker ────────────────────────────────────────────────────────────────

def rerank_evidence(evidence_pool: list) -> list:
    """
    Scores articles by: content length × relevance × stance diversity bonus
    − source repetition penalty + contrarian boost.
    """
    stance_counts: dict = {}
    source_counts: dict = {}
    scored = []

    for doc in evidence_pool:
        content_len = len(doc.get("content", ""))
        stance  = doc.get("stance", "neutral")
        source  = doc.get("metadata", {}).get("source_name", "unknown")
        rel     = doc.get("_relevance_score", 0.5)

        stance_counts[stance] = stance_counts.get(stance, 0) + 1
        source_counts[source] = source_counts.get(source, 0) + 1

        relevance_score  = min(content_len / 500, 3.0) * (1 + rel)
        source_penalty   = min(source_counts[source] - 1, 2) * 0.5
        stance_bonus     = 0.8 if stance_counts[stance] <= 2 else 0.0
        contrarian_boost = 1.0 if stance in ("skeptical", "critical", "mixed") else 0.0

        total = relevance_score - source_penalty + stance_bonus + contrarian_boost
        scored.append((total, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored]


# ── Node ────────────────────────────────────────────────────────────────────

class AuditorNode:
    def __init__(self, model):
        self.model = model

    def __call__(self, state: AgentState):
        user_query    = state.get("query", "")
        evidence_list = state.get("evidence_pool", [])

        # Hard guardrail: nothing retrieved
        if not evidence_list:
            return {
                "claims": [],
                "weak_contrarian_signal": True,
                "skip_contrarian": True,
                "final_report": (
                    f"## No Data Found\n\n"
                    f"No news articles were retrieved for: **{user_query}**\n\n"
                    "**Possible causes:**\n"
                    "- OpenSearch index is empty — trigger the Airflow DAG to ingest RSS feeds\n"
                    "- Query terms too niche for current index content\n"
                    "- OpenSearch connection issue\n\n"
                    "_No analysis generated. No facts were invented._"
                ),
            }

        # ── Topic relevance gate ─────────────────────────────────────────
        relevant_evidence = []
        for doc in evidence_list:
            combined = (
                doc.get("content", "") + " " +
                doc.get("metadata", {}).get("title", "")
            )
            score = topic_relevance_score(user_query, combined)
            if score >= MIN_RELEVANCE_SCORE:
                doc["_relevance_score"] = score
                relevant_evidence.append(doc)
            else:
                print(
                    f"[AuditorNode] Dropped off-topic (score={score:.2f}): "
                    f"{doc.get('metadata', {}).get('title', 'untitled')[:60]}"
                )

        if not relevant_evidence:
            return {
                "claims": [],
                "weak_contrarian_signal": True,
                "skip_contrarian": True,
                "final_report": (
                    f"## Insufficient On-Topic Coverage\n\n"
                    f"**Query:** {user_query}\n\n"
                    f"{len(evidence_list)} articles retrieved but none matched the query topic "
                    f"(relevance threshold: {MIN_RELEVANCE_SCORE:.0%}).\n\n"
                    "Re-trigger the Airflow ingest DAG or rephrase the query.\n\n"
                    "_No analysis generated. No facts were invented._"
                ),
            }

        print(
            f"[AuditorNode] {len(relevant_evidence)}/{len(evidence_list)} "
            "articles passed topic gate."
        )

        # ── Stance classification ────────────────────────────────────────
        for doc in relevant_evidence:
            doc["stance"] = classify_stance(doc.get("content", ""))

        # ── Rerank ──────────────────────────────────────────────────────
        ranked      = rerank_evidence(relevant_evidence)
        top_evidence = ranked[:TOP_K]

        contrarian_count = sum(
            1 for d in top_evidence
            if d.get("stance") in ("skeptical", "critical", "mixed")
        )
        weak_signal = contrarian_count < MIN_CONTRARIAN

        evidence_context = json.dumps([
            {
                "source_id":       d["source_id"],
                "url":             d["url"],
                "stance":          d["stance"],
                "source_category": d.get("source_category", ""),
                "title":           d.get("metadata", {}).get("title", ""),
                "content":         d["content"][:400],
            }
            for d in top_evidence
        ], indent=2)

        # ── Auditor LLM prompt ───────────────────────────────────────────
        # CHANGELOG: tightened "NO external knowledge" guard; made friction_point
        # requirement explicit; kept JSON-only output instruction.
        prompt = f"""You are a strict evidence auditor. Extract verifiable friction points from the evidence below.

TOPIC LOCK — CRITICAL: This analysis is ONLY about: "{user_query}"
If any evidence item is NOT about this topic, ignore it entirely.
If the evidence as a whole is not about "{user_query}", return exactly: []

USER QUERY: {user_query}

EVIDENCE (pre-filtered for topic relevance, ranked by stance/source diversity):
{evidence_context}

RULES — MUST FOLLOW:
1. Use ONLY facts explicitly stated in the EVIDENCE above. NO external knowledge.
2. Do NOT fabricate quotes, statistics, or source names not in the evidence.
3. Every claim MUST cite an actual source_id from the evidence list above.
4. If evidence does not support a friction point about "{user_query}", omit it.
5. friction_point must directly relate to "{user_query}" — not a tangential topic.

OUTPUT: Return ONLY a valid JSON array. No preamble, no markdown fences, no explanation.
Schema per item:
{{
  "friction_point": "short title of the tension (must relate to {user_query})",
  "consensus_claim": "what mainstream sources say [source_id]",
  "contrarian_evidence": "what skeptical/critical sources say [source_id]",
  "source_id": "primary source_id",
  "url": "primary source url",
  "stance": "supportive|neutral|skeptical|critical|mixed"
}}

If no genuine on-topic friction point exists: []
"""

        response = self.model.invoke(prompt)
        content  = response.content if hasattr(response, "content") else str(response)

        try:
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            claims = json.loads(json_match.group()) if json_match else []
        except Exception as e:
            print(f"[AuditorNode] JSON parse error: {e}")
            claims = []

        return {
            "claims":                 claims,
            "evidence_pool":          ranked,
            "weak_contrarian_signal": weak_signal,
            "skip_contrarian":        False,
        }
