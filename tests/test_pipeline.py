# tests/test_pipeline.py
# ── CHANGELOG ──────────────────────────────────────────────────────────────
# NEW FILE. Replaces thin test_agents.py stub.
# - Covers 7 domains: technology, economy, science, health, politics,
#   environment, and social policy.
# - Uses a MockSearchService (no OpenSearch or LLM needed) to test:
#   (a) query expansion, (b) topic relevance gate, (c) stance classification,
#   (d) reranking, (e) contrarian fallback paths.
# - Verifies: no hallucination (all cited source_ids exist in retrieved pool),
#   generic pipeline (no domain-specific regression), fallback on weak signal.
# ───────────────────────────────────────────────────────────────────────────

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import re
import pytest

from app.agents.nodes.researcher import expand_queries, ResearcherNode
from app.agents.nodes.auditor    import (
    AuditorNode, classify_stance, topic_relevance_score, rerank_evidence
)
from app.agents.nodes.perspective import PerspectiveAnalystNode
from app.agents.nodes.contrarian  import ContrarianNode
from app.config import (
    SOURCE_CATEGORIES, EXTRA_VARIANTS,
    MIN_RELEVANCE_SCORE, MIN_CONTRARIAN,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

class MockSearchService:
    """
    Returns plausible fake articles for any query.
    Injects at least two skeptical articles per batch to exercise contrarian path.
    """
    def search(self, query: str, page_size: int = 10) -> list:
        # Extract first meaningful word from query as pseudo-topic
        tokens = [t for t in query.split() if len(t) > 3]
        topic  = tokens[0] if tokens else "topic"

        results = []
        stances = ["positive growth reported", "concerns and risks identified",
                   "backlash criticism warns", "analysis review data", "decline failure challenge"]
        for i in range(min(page_size, 5)):
            stance_text = stances[i % len(stances)]
            results.append({
                "title":       f"{topic.capitalize()} Update {i+1}",
                "description": f"Report on {topic}: {stance_text} in latest developments.",
                "url":         f"https://example.com/{topic}-{i+1}",
                "publishedAt": "2026-05-01T00:00:00Z",
                "source":      {"name": f"Source{i+1}"},
            })
        return results


class MockLLM:
    """
    Returns deterministic, valid outputs for each node's LLM call.
    Prevents real API calls during tests.
    """
    def invoke(self, prompt: str):
        # Perspective node: return 3 generic gaps
        if "editorial diversity auditor" in prompt:
            return _Resp(
                "1. Trade press coverage: missing industry-specific data.\n"
                "2. Regional outlets: local impact not represented.\n"
                "3. Analyst notes: expert financial perspective absent."
            )
        # Auditor node: return valid friction-point JSON
        if "evidence auditor" in prompt:
            return _Resp(json.dumps([{
                "friction_point":       "Mainstream vs skeptical assessment",
                "consensus_claim":      "Sources report positive trends [NEWS_1]",
                "contrarian_evidence":  "Other sources cite risks and decline [NEWS_2]",
                "source_id":            "NEWS_2",
                "url":                  "https://example.com/topic-2",
                "stance":               "skeptical",
            }]))
        # Contrarian node: return structured report
        if "Senior Contrarian Editor" in prompt:
            # Extract query from prompt (between first pair of quotes after "about:")
            m = re.search(r'about: "([^"]+)"', prompt)
            q = m.group(1) if m else "the topic"
            return _Resp(
                f"## Mainstream Narrative\n"
                f"Sources report consensus view on {q} [NEWS_1].\n\n"
                f"## Contrarian View\n"
                f"Skeptical sources identify risks in {q} [NEWS_2].\n\n"
                f"## Evidence\n"
                f"NEWS_2 documents specific challenges related to {q}.\n\n"
                f"## Caveats\n"
                f"Analysis limited by current index coverage of {q}."
            )
        return _Resp("[]")


class _Resp:
    def __init__(self, text):
        self.content = text


# ── Test queries (7 domains) ─────────────────────────────────────────────────

TEST_QUERIES = [
    ("technology",   "artificial intelligence regulation"),
    ("economy",      "inflation interest rates impact"),
    ("science",      "climate tipping points research"),
    ("health",       "mRNA vaccine long-term effects"),
    ("politics",     "electoral reform voting systems"),
    ("environment",  "ocean plastic pollution solutions"),
    ("social",       "universal basic income pilots"),
]


# ── Unit tests ───────────────────────────────────────────────────────────────

class TestQueryExpansion:
    def test_returns_list_of_tuples(self):
        variants = expand_queries("test topic")
        assert isinstance(variants, list)
        assert all(isinstance(v, tuple) and len(v) == 2 for v in variants)

    def test_covers_all_source_categories(self):
        variants  = expand_queries("test topic")
        labels    = [label for _, label in variants]
        expected  = [cat for cat, _ in SOURCE_CATEGORIES]
        for cat in expected:
            assert cat in labels, f"Category '{cat}' missing from variants"

    def test_no_hardcoded_domain_terms(self):
        """Expansion suffixes must not contain any domain-specific topic words."""
        domain_words = {
            "ai", "crypto", "bitcoin", "layoffs", "politics", "election",
            "climate", "vaccine", "covid", "stock", "market",
        }
        variants = expand_queries("neutral query")
        for query, _ in variants:
            tokens = set(query.lower().split())
            intersection = tokens & domain_words
            # Allow 'neutral' and 'query' — only flag real domain injection
            injected = intersection - {"neutral", "query"}
            assert not injected, f"Domain-specific term injected: {injected} in '{query}'"

    @pytest.mark.parametrize("domain,query", TEST_QUERIES)
    def test_expansion_generic_across_domains(self, domain, query):
        variants = expand_queries(query)
        assert len(variants) >= len(SOURCE_CATEGORIES) + len(EXTRA_VARIANTS) - 1
        print(f"\n[{domain}] '{query}' → {len(variants)} variants:")
        for q, cat in variants:
            print(f"  [{cat}] {q}")


class TestStanceClassification:
    @pytest.mark.parametrize("text,expected", [
        ("breakthrough success growth record high", "supportive"),
        ("concerns risks backlash criticism warns", "skeptical"),
        ("collapse crisis fraud disaster fails",    "critical"),
        ("growth gains but risks and concerns",     "mixed"),
        ("report study analysis review data",       "neutral"),
        ("",                                        "neutral"),
    ])
    def test_classify_stance(self, text, expected):
        assert classify_stance(text) == expected


class TestTopicRelevance:
    def test_on_topic_article(self):
        score = topic_relevance_score("climate change", "climate scientists warn of change")
        assert score >= MIN_RELEVANCE_SCORE

    def test_off_topic_article(self):
        score = topic_relevance_score("interest rates inflation", "sports team wins championship game")
        assert score < MIN_RELEVANCE_SCORE

    def test_empty_query_passes(self):
        score = topic_relevance_score("", "any content here")
        assert score == 1.0


class TestReranking:
    def test_contrarian_articles_ranked_higher(self):
        pool = [
            {"content": "x" * 200, "stance": "supportive", "metadata": {"source_name": "A"}, "_relevance_score": 0.5},
            {"content": "x" * 200, "stance": "critical",   "metadata": {"source_name": "B"}, "_relevance_score": 0.5},
            {"content": "x" * 200, "stance": "neutral",    "metadata": {"source_name": "C"}, "_relevance_score": 0.5},
        ]
        ranked = rerank_evidence(pool)
        top_stance = ranked[0]["stance"]
        assert top_stance in ("critical", "skeptical", "mixed"), \
            f"Expected contrarian article ranked first, got '{top_stance}'"

    def test_source_diversity_penalty(self):
        # Verify penalty reduces score of repeated sources.
        # Mix: 3× SAME (heavy repeat), 1× DIFF with higher relevance — DIFF should outrank 3rd SAME.
        pool = [
            {"content": "x" * 300, "stance": "neutral", "metadata": {"source_name": "SAME"}, "_relevance_score": 0.8},
            {"content": "x" * 300, "stance": "neutral", "metadata": {"source_name": "SAME"}, "_relevance_score": 0.8},
            {"content": "x" * 300, "stance": "neutral", "metadata": {"source_name": "SAME"}, "_relevance_score": 0.8},
            {"content": "x" * 300, "stance": "neutral", "metadata": {"source_name": "DIFF"}, "_relevance_score": 0.8},
        ]
        ranked = rerank_evidence(pool)
        sources = [d["metadata"]["source_name"] for d in ranked]
        # Third SAME (max penalty = 1.0) should rank behind DIFF
        last_same_idx  = max(i for i, s in enumerate(sources) if s == "SAME")
        diff_idx       = sources.index("DIFF")
        assert diff_idx < last_same_idx, (
            f"Source diversity penalty insufficient: ordering={sources}"
        )


# ── Integration tests (full pipeline per domain) ─────────────────────────────

class TestFullPipeline:
    """
    Runs researcher → auditor → perspective → contrarian for each domain
    using MockSearchService and MockLLM.
    Verifies: source_ids cited in report exist in evidence pool; no hallucination.
    """

    @pytest.mark.parametrize("domain,query", TEST_QUERIES)
    def test_pipeline_end_to_end(self, domain, query):
        mock_search = MockSearchService()
        mock_llm    = MockLLM()

        state = {
            "query":                  query,
            "evidence_pool":          [],
            "claims":                 [],
            "missing_perspectives":   [],
            "weak_contrarian_signal": False,
            "skip_contrarian":        False,
            "final_report":           None,
            "report_id":              None,
        }

        # ── Researcher ──────────────────────────────────────────────────
        researcher = ResearcherNode(mock_search)
        r_out = researcher(state)
        state["evidence_pool"] = r_out["evidence_pool"]

        print(f"\n[{domain}] '{query}'")
        print(f"  Retrieved: {len(state['evidence_pool'])} articles")
        for d in state["evidence_pool"][:3]:
            print(f"    [{d['source_id']}] [{d['source_category']}] "
                  f"{d['metadata']['title'][:60]}")

        assert len(state["evidence_pool"]) > 0, "No articles retrieved"

        # ── Auditor ─────────────────────────────────────────────────────
        auditor = AuditorNode(mock_llm)
        a_out = auditor(state)
        state.update(a_out)

        print(f"  After auditor: {len(state.get('evidence_pool',[]))} relevant, "
              f"claims={len(state.get('claims',[]))}, "
              f"weak={state.get('weak_contrarian_signal')}, "
              f"skip={state.get('skip_contrarian')}")

        stances = {d["stance"] for d in state.get("evidence_pool", [])}
        print(f"  Stances present: {stances}")

        if state.get("skip_contrarian"):
            print(f"  → Hard-stop triggered: {state.get('final_report','')[:80]}")
            return  # No further nodes run — acceptable

        # ── Perspective ─────────────────────────────────────────────────
        perspective = PerspectiveAnalystNode(mock_llm)
        p_out = perspective(state)
        state["missing_perspectives"] = p_out["missing_perspectives"]
        print(f"  Missing perspectives: {state['missing_perspectives']}")
        assert len(state["missing_perspectives"]) <= 3

        # ── Contrarian ──────────────────────────────────────────────────
        contrarian = ContrarianNode(mock_llm)
        c_out = contrarian(state)
        if c_out:
            state["final_report"] = c_out.get("final_report", state.get("final_report"))

        report = state.get("final_report", "")
        assert report, "No final report generated"
        print(f"  Report ({len(report)} chars): {report[:120]}...")

        # ── Anti-hallucination check ─────────────────────────────────────
        cited_ids = set(re.findall(r'NEWS_\d+', report))
        pool_ids  = {d["source_id"] for d in state["evidence_pool"]}
        phantom   = cited_ids - pool_ids
        assert not phantom, (
            f"[{domain}] Hallucinated source_ids in report: {phantom}. "
            f"Pool had: {pool_ids}"
        )
        print(f"  ✓ Anti-hallucination: cited={cited_ids}, all in pool")

    def test_empty_index_fallback(self):
        """Pipeline gracefully handles zero results from search."""
        class EmptySearch:
            def search(self, q, page_size=10): return []

        state = {
            "query": "very niche obscure topic xyz123",
            "evidence_pool": [], "claims": [],
            "missing_perspectives": [],
            "weak_contrarian_signal": False,
            "skip_contrarian": False,
            "final_report": None, "report_id": None,
        }
        state["evidence_pool"] = ResearcherNode(EmptySearch())(state)["evidence_pool"]
        a_out = AuditorNode(MockLLM())(state)
        state.update(a_out)

        assert state.get("skip_contrarian") is True
        assert "No Data Found" in state.get("final_report", "")
        print(f"\n[empty-index] Fallback: {state['final_report'][:80]}")

    def test_off_topic_results_fallback(self):
        """Pipeline hard-stops when all retrieved articles are off-topic."""
        class OffTopicSearch:
            def search(self, q, page_size=10):
                return [{
                    "title": "Sports result championship", "description": "Team wins game",
                    "url": f"https://sports.com/{i}", "publishedAt": "2026-01-01",
                    "source": {"name": "SportsCo"},
                } for i in range(5)]

        state = {
            "query": "monetary policy central bank interest rates",
            "evidence_pool": [], "claims": [],
            "missing_perspectives": [],
            "weak_contrarian_signal": False,
            "skip_contrarian": False,
            "final_report": None, "report_id": None,
        }
        state["evidence_pool"] = ResearcherNode(OffTopicSearch())(state)["evidence_pool"]
        a_out = AuditorNode(MockLLM())(state)
        state.update(a_out)

        assert state.get("skip_contrarian") is True, \
            "Should hard-stop on off-topic evidence"
        print(f"\n[off-topic] Fallback: {state.get('final_report','')[:80]}")


# ── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Allow running directly: python tests/test_pipeline.py
    import unittest
    loader  = unittest.TestLoader()
    suite   = unittest.TestSuite()
    for cls in [
        TestQueryExpansion, TestStanceClassification,
        TestTopicRelevance, TestReranking, TestFullPipeline,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
