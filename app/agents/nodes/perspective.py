from app.agents.state import AgentState
from app.config import SOURCE_TYPE_CHECKLIST


class PerspectiveAnalystNode:
    def __init__(self, model):
        self.model = model

    def __call__(self, state: AgentState):
        evidence_pool = state.get("evidence_pool", [])

        # Summarise what source categories are actually present
        present_categories = set(d.get("source_category", "unknown") for d in evidence_pool)
        stances_present = set(d.get("stance", "unclassified") for d in evidence_pool)

        evidence_summary = "\n".join([
            f"- [{d.get('source_id')}] ({d.get('source_category','?')}, {d.get('stance','?')}): "
            f"{d.get('content','')[:150]}"
            for d in evidence_pool[:15]
        ])

        prompt = f"""You are an editorial diversity auditor. Identify SPECIFIC missing source types.

SOURCE CATEGORIES ALREADY RETRIEVED: {', '.join(present_categories) or 'none'}
STANCES ALREADY PRESENT: {', '.join(stances_present) or 'none'}

SOURCE TYPE CHECKLIST (identify which are MISSING from retrieved evidence):
{chr(10).join(f'- {s}' for s in SOURCE_TYPE_CHECKLIST)}

EVIDENCE SAMPLE:
{evidence_summary}

RULES:
1. Only flag source types genuinely absent from the evidence sample.
2. Be specific: name the missing type and why it matters for understanding this topic.
3. Do NOT suggest types that are already represented.
4. Return exactly 3 missing perspectives as a numbered list. No preamble.

FORMAT:
1. [missing source type]: [why it matters for this topic — 1 sentence]
2. [missing source type]: [why it matters]
3. [missing source type]: [why it matters]
"""

        response = self.model.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        gaps = self.parse_gaps(content)

        return {"missing_perspectives": gaps}

    def parse_gaps(self, text: str) -> list:
        """Parse numbered list into clean strings. Graceful fallback."""
        if not text:
            return [
                "Trade press perspective missing",
                "Regional impact data missing",
                "Primary source interviews missing",
            ]

        lines = text.strip().split("\n")
        clean = []
        for line in lines:
            line = line.strip().lstrip("0123456789.-*• ")
            if line:
                clean.append(line)
        return clean[:3] if clean else [
            "Analyst commentary missing",
            "Regulatory perspective missing",
            "Community impact assessment missing",
        ]
