import streamlit as st


def render_evidence_board(state: dict):
    st.header("🕵️ Evidence Graph & Traceability")

    evidence_pool = state.get("evidence_pool", [])
    ev_by_id = {e["source_id"]: e for e in evidence_pool}

    for claim in state.get("claims", []):
        # Support both old schema ('text') and new schema ('friction_point')
        title = claim.get("friction_point") or claim.get("text", "Unnamed claim")

        with st.expander(f"Claim: {title}"):
            reasoning = claim.get("reasoning_step", "")
            if reasoning:
                st.write(f"**Reasoning:** {reasoning}")

            # New schema: single source_id on claim
            source_id = claim.get("source_id")
            evidence_ids = claim.get("evidence_ids", [])
            ids_to_show = ([source_id] if source_id else []) + list(evidence_ids)
            ids_to_show = list(dict.fromkeys(ids_to_show))  # dedup, preserve order

            for ev_id in ids_to_show:
                ev = ev_by_id.get(ev_id)
                if ev:
                    # Support both old 'sentiment_alignment' and new 'stance'
                    stance = ev.get("stance") or ev.get("sentiment_alignment", "neutral")
                    color = {
                        "supportive": "green", "supporting": "green",
                        "critical": "red",    "contradicting": "red",
                        "skeptical": "orange", "mixed": "orange",
                    }.get(stance.lower(), "grey")

                    col1, col2 = st.columns([1, 4])
                    col1.markdown(f":{color}[{stance.title()}]")
                    col2.info(f"{ev.get('content', '')[:300]}\n\n[Source]({ev.get('url', '#')})")

    if state.get("missing_perspectives"):
        st.warning(f"**Editorial Blindspots:** {', '.join(state['missing_perspectives'])}")
