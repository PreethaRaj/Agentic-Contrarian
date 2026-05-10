from typing import Annotated, List, TypedDict, Optional
import operator

class Evidence(TypedDict):
    source_id: str
    content: str
    url: str
    source_category: str          # NEW: mainstream/opinion/trade/regional/analyst/etc.
    stance: str                   # NEW: supportive/neutral/skeptical/critical/mixed
    metadata: dict
    confidence_score: float
    sentiment_alignment: str  # "Supporting", "Contradicting", "Neutral"

class Claim(TypedDict):
    friction_point: str           # renamed from 'text' to match auditor output schema
    consensus_claim: str
    contrarian_evidence: str
    source_id: str
    url: str
    stance: str
    reasoning_step: str  # The logic used to bridge evidence to claim

class AgentState(TypedDict):
    query: str
    # Annotated with operator.add so nodes can append to the pool
    evidence_pool: Annotated[List[Evidence], operator.add]
    claims: List[Claim]
    missing_perspectives: List[str]
    weak_contrarian_signal: bool  # NEW: triggers fallback in ContrarianNode
    skip_contrarian:         bool    # NEW: bypasses ContrarianNode when True
    final_report: Optional[str]
    report_id: Optional[str]  # UUID for shareable reports