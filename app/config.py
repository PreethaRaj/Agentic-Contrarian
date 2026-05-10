# app/config.py
# ── CHANGELOG ──────────────────────────────────────────────────────────────
# NEW FILE. Centralises every tuneable and every domain-agnostic string so
# nodes never hard-code topic-specific wording. Edit here, not in node files.
# ───────────────────────────────────────────────────────────────────────────

# ── Retrieval ───────────────────────────────────────────────────────────────
MAX_RESULTS_TOTAL   = 40   # hard cap across all query variants
TOP_K_RERANKED      = 12   # articles passed to auditor prompt
TOP_K_EVIDENCE      = 10   # articles passed to contrarian prompt
MIN_CONTRARIAN      = 2    # minimum skeptical/critical articles before weak-signal flag
MIN_RELEVANCE_SCORE = 0.40  # 40% keyword match required

# ── Generic query-expansion suffixes (domain-agnostic) ──────────────────────
# Each tuple: (category_label, search_suffix_appended_to_base_query)
# Add/remove rows to tune coverage without touching node code.
SOURCE_CATEGORIES = [
    ("mainstream",  ""),
    ("opinion",     "opinion OR editorial OR commentary OR perspective"),
    ("trade",       "industry analysis OR sector report OR trade publication"),
    ("regional",    "local impact OR regional OR community"),
    ("analyst",     "analyst OR research OR expert OR interview"),
    ("explainer",   "explainer OR background OR deep dive OR context"),
    ("skeptical",   "criticism OR risks OR downside OR problems OR challenges"),
    ("policy",      "policy OR regulation OR legislation OR government response"),
    ("impact",      "impact OR consequences OR effects OR outcome"),
]
# Extra framing variants appended after SOURCE_CATEGORIES
EXTRA_VARIANTS = [
    # (template with {q} placeholder, category_label)
    ("against {q} OR {q} problems OR {q} failure",   "skeptical"),
    ("{q} policy implications OR {q} regulation",     "policy"),
    ("{q} alternative explanation OR {q} causes",     "alternative"),
    ("{q} opinion editorial",                          "editorial"),
]

# ── Stance classification signals (generic vocabulary) ──────────────────────
SUPPORTIVE_SIGNALS = {
    "breakthrough", "success", "growth", "positive", "gains", "soars",
    "record", "surge", "advance", "improves", "achieves", "landmark",
    "gain",  # singular form
}
SKEPTICAL_SIGNALS = {
    "concern", "concerns", "risk", "risks", "doubt", "criticism", "backlash",
    "against", "problems", "challenge", "challenges", "failure", "decline",
    "warns", "caution", "uncertainty", "disputed", "questioned", "controversial",
    "mixed", "uneven", "hard", "difficult", "difficulty", "hurdle", "hurdles",
    "struggle", "struggles", "obstacle", "obstacles", "friction", "barrier",
    "barriers", "limited", "limiting", "slow", "slowing", "lag", "lagging",
    "despite", "however", "although", "tension", "tensions", "gap", "gaps",
    "issue", "issues", "flaw", "flaws", "downside", "downsides", "setback",
    "setbacks", "underperform", "underwhelming", "volatile", "volatility",
}
CRITICAL_SIGNALS = {
    "collapse", "crisis", "fraud", "scandal", "fails", "disaster",
    "catastrophe", "catastrophic", "corruption", "cover-up", "exposed",
}
NEUTRAL_SIGNALS = {
    "report", "study", "analysis", "review", "survey", "data", "figures",
    "statistics", "according", "shows", "indicates", "finds",
}

# ── Source-diversity checklist for PerspectiveAnalystNode ───────────────────
SOURCE_TYPE_CHECKLIST = [
    "trade press / industry publications",
    "regional or local news outlets",
    "analyst notes or research reports",
    "government or regulatory sources",
    "academic or think-tank commentary",
    "first-person interviews or primary sources",
    "opinion/editorial from affected communities",
    "niche or specialist publications",
]

# ── Stop words for relevance scoring ────────────────────────────────────────
STOP_WORDS = {
    "is","are","the","a","an","of","in","to","and","or","for","on","at",
    "by","this","that","with","from","be","been","toward","towards","about",
    "it","its","not","do","does","did","was","were","has","have","had",
    "will","would","could","should","may","might","also","but","if","as",
}
