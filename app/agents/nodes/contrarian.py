import re
from app.agents.state import AgentState
from app.config import TOP_K_EVIDENCE, STOP_WORDS


def _query_keywords(query: str) -> set:
    return set(re.findall(r'\b\w+\b', query.lower())) - STOP_WORDS


def _report_on_topic(report: str, query_keywords: set) -> bool:
    """True if generated report contains ≥1 meaningful query keyword."""
    if not query_keywords:
        return True
    report_tokens = set(re.findall(r'\b\w+\b', report.lower()))
    return bool(query_keywords & report_tokens)


class ContrarianNode:
    def __init__(self, model):
        self.model = model

    def __call__(self, state: AgentState):
        user_query  = state.get("query", "")
        weak_signal = state.get("weak_contrarian_signal", False)
        skip        = state.get("skip_contrarian", False)
        evidence    = state.get("evidence_pool", [])[:TOP_K_EVIDENCE]
        claims      = state.get("claims", [])
        blindspots  = state.get("missing_perspectives", [])
        query_kws   = _query_keywords(user_query)

        # ── Hard skip: AuditorNode already set final_report ──────────────
        if skip:
            print("[ContrarianNode] Skipped — AuditorNode hard-stop active.")
            return {}

        # ── Weak-signal fallback (no LLM call, honest message) ───────────
        if weak_signal and not claims:
            output_text = (
                f"## Analysis: {user_query}\n\n"
                "**Mainstream Narrative:** Retrieved sources predominantly reflect "
                "a consensus view on this topic.\n\n"
                "**Contrarian View:** Insufficient direct contrarian coverage found "
                "in the current index. The absence of dissenting sources may itself "
                "be a signal worth noting.\n\n"
                "**Evidence:** No verified skeptical or critical sources returned.\n\n"
                "**Caveats:** Analysis limited by available indexed sources. "
                "Re-trigger the ingest DAG or broaden the query.\n\n"
                f"**Missing Perspectives:** "
                f"{'; '.join(blindspots) if blindspots else 'Not assessed.'}"
            )
            print("[ContrarianNode] Weak signal — fallback used, no LLM call.")
            return {"final_report": output_text}

        # ── Build evidence block ─────────────────────────────────────────
        evidence_block = "\n".join([
            f"[{d.get('source_id')}] ({d.get('stance','?')}) "
            f"{d.get('metadata',{}).get('title','')} — {d.get('content','')[:250]}"
            for d in evidence
        ])

        claims_block = "\n".join([
            f"- {c.get('friction_point','')}: mainstream='{c.get('consensus_claim','')}' "
            f"vs contrarian='{c.get('contrarian_evidence','')}' [src:{c.get('source_id','')}]"
            for c in claims
        ]) or "No verified friction points extracted."

        # ── LLM prompt ───────────────────────────────────────────────────
        # CHANGELOG: each section now has an explicit "CITATION REQUIRED" note;
        # removed any domain-specific framing; shortened section limit to 2–4 sentences.
        prompt = f"""You are a Senior Contrarian Editor. Produce a structured intelligence briefing.

══ TOPIC LOCK — READ FIRST ══
Your ENTIRE response must be about: "{user_query}"
If you find yourself writing about any other topic, STOP and return:
"## Off-Topic Guard\\nInsufficient on-topic evidence for: {user_query}"
══════════════════════════════

QUERY: {user_query}

EVIDENCE (pre-validated for topic relevance — source_id, stance, excerpt):
{evidence_block}

VERIFIED FRICTION POINTS (from evidence only):
{claims_block}

IDENTIFIED GAPS: {'; '.join(blindspots) if blindspots else 'None identified.'}

STRICT RULES:
1. Use ONLY facts from the EVIDENCE above. Cite source_ids inline like [NEWS_1].
2. Do NOT invent statistics, quotes, names, or events not present in the evidence.
3. If you cannot cite a source_id for a statement, omit the statement entirely.
4. Each section: 2–4 sentences maximum. Be concise and specific.
5. Every sentence must relate to "{user_query}" — not any other topic.
6. CITATION REQUIRED in every section. Unsourced claims will be flagged as hallucinations.

FORMAT — use exactly these headers, no additional headers:

## Mainstream Narrative
[What most retrieved sources say about {user_query}. CITATION REQUIRED per claim.]

## Contrarian View
[Non-consensus interpretation from skeptical/critical sources. CITATION REQUIRED.]

## Evidence
[Specific facts from sources supporting the contrarian view. Each point cites a source_id.]

## Caveats
[Missing evidence, underrepresented stances, and reasons the contrarian view may be wrong.]
"""

        response    = self.model.invoke(prompt)
        output_text = response.content if hasattr(response, "content") else str(response)

        # ── Post-generation topic check ───────────────────────────────────
        if not _report_on_topic(output_text, query_kws):
            print(
                f"[ContrarianNode] Off-topic output detected. "
                f"Expected keywords: {query_kws}. Using honest fallback."
            )
            output_text = (
                f"## Analysis: {user_query}\n\n"
                "**Mainstream Narrative:** Retrieved sources did not produce "
                "sufficient on-topic content for a reliable analysis.\n\n"
                "**Contrarian View:** Cannot be generated without verified on-topic evidence.\n\n"
                "**Evidence:** None confirmed for this query in the current index.\n\n"
                "**Caveats:** The index may lack recent articles on this specific topic. "
                "Re-trigger the Airflow ingest DAG and retry.\n\n"
                f"**Missing Perspectives:** "
                f"{'; '.join(blindspots) if blindspots else 'Not assessed.'}"
            )

        print(f"[ContrarianNode] Report done ({len(output_text)} chars).")
        return {"final_report": output_text}
