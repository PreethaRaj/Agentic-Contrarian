import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import re
import streamlit as st
import requests
import time
import uuid
from fpdf import FPDF
from dotenv import load_dotenv
load_dotenv()

# ── Dev mode: set env var DEV_MODE=1 before launching, or pass ?dev=1 in URL
# Usage:  DEV_MODE=1 streamlit run app/ui/dashboard.py
# CHANGELOG Issue 4: debug tab hidden by default, only shown in dev mode.
DEV_MODE = (
    os.getenv("DEV_MODE", "0") == "1"
    or st.query_params.get("dev", "0") == "1"
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agentic-Contrarian Research Suite",
    page_icon="🕵️",
    layout="wide",
)

st.markdown("""
<style>
.stApp { background-color: #0d1117; color: #c9d1d9; }
.response-box {
    padding: 25px; border-radius: 12px;
    border: 1px solid #30363d; background-color: #161b22;
    line-height: 1.8; font-size: 1.05rem; margin-bottom: 20px;
}
.response-box a.cite {
    color: #58a6ff; font-size: 0.85rem;
    text-decoration: none; border-bottom: 1px dotted #58a6ff;
}
.response-box a.cite:hover { color: #79c0ff; }
.stButton>button {
    background-image: linear-gradient(to right, #238636, #2ea043);
    color: white; border: none; font-weight: bold; width: 100%;
}
[data-testid="stMetricValue"] { color: #58a6ff; font-family: 'Courier New', monospace; }
.badge {
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 0.78rem; font-weight: bold; margin-left: 6px;
}
.badge-supportive  { background:#1a4731; color:#3fb950; }
.badge-skeptical   { background:#3d2b00; color:#e3b341; }
.badge-critical    { background:#3d1414; color:#f85149; }
.badge-mixed       { background:#2d2d00; color:#d29922; }
.badge-neutral     { background:#21262d; color:#8b949e; }
.badge-unclassified{ background:#21262d; color:#8b949e; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def build_url_map(evidence_pool: list) -> dict:
    m = {}
    for d in evidence_pool:
        sid = d.get("source_id", "")
        m[sid] = {
            "url":    d.get("url", ""),
            "title":  d.get("metadata", {}).get("title", sid),
            "source": d.get("metadata", {}).get("source_name", ""),
        }
    return m


def linkify_report(report_md: str, url_map: dict) -> str:
    """Replace [NEWS_X] tokens with clickable <a> links."""
    def replace_citation(match):
        sid  = match.group(1)
        info = url_map.get(sid, {})
        url  = info.get("url", "")
        src  = info.get("source", sid)
        if url:
            return f'<a class="cite" href="{url}" target="_blank">[{sid} · {src}]</a>'
        return f"**[{sid}]**"
    return re.sub(r'\[(NEWS_\d+)\]', replace_citation, report_md)


def stance_badge(stance: str) -> str:
    cls = f"badge-{stance.lower().replace(' ', '-')}"
    return f'<span class="badge {cls}">{stance.upper()}</span>'


def create_pdf(report_text: str, query: str, evidence_pool: list, claims: list) -> bytes:
    """PDF export: query, report, evidence table, friction points."""

    class _PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 14)
            self.set_text_color(40, 40, 40)
            self.cell(0, 10, "Contrarian Intelligence Briefing", ln=True, align="C")
            self.ln(2)
        def footer(self):
            self.set_y(-12)
            self.set_font("Arial", "I", 8)
            self.set_text_color(150, 150, 150)
            txt = f"Page {self.page_no()} - Agentic-Contrarian"
            self.cell(0, 10, txt.encode("latin-1","replace").decode("latin-1"), align="C")

    def safe(text: str) -> str:
        return (text or "").encode("latin-1", "replace").decode("latin-1")

    def section_title(pdf, title):
        """Reset X, draw bold section heading, underline."""
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", "B", 12)
        pdf.set_text_color(30, 80, 180)
        pdf.cell(0, 8, title, ln=True)
        # Draw line using effective page width — never hardcode 200
        pdf.set_draw_color(180, 180, 200)
        y = pdf.get_y()
        pdf.line(pdf.l_margin, y, pdf.l_margin + pdf.epw, y)
        pdf.ln(3)
        pdf.set_text_color(50, 50, 50)

    pdf = _PDF()
    pdf.set_margins(15, 15, 15)          # left, top, right — all 15mm
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    W = pdf.epw  # effective page width — always correct regardless of margins

    # ── Subject ───────────────────────────────────────────────────────────
    section_title(pdf, "Subject")
    pdf.set_font("Arial", size=10)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(W, 6, safe(query))
    pdf.ln(5)

    # ── Executive analysis ────────────────────────────────────────────────
    section_title(pdf, "Executive Analysis")
    pdf.set_font("Arial", size=9)
    pdf.set_x(pdf.l_margin)
    clean = re.sub(r'<[^>]+>', '', report_text)   # strip HTML citation links
    pdf.multi_cell(W, 5, safe(clean))
    pdf.ln(5)

    # ── Evidence table ────────────────────────────────────────────────────
    if evidence_pool:
        pdf.add_page()
        section_title(pdf, f"Evidence Pool  ({len(evidence_pool)} sources)")

        # Column widths as fractions of W — always safe
        c_id     = round(W * 0.09)   # ~17mm
        c_stance = round(W * 0.14)   # ~25mm
        c_src    = round(W * 0.22)   # ~40mm
        c_title  = W - c_id - c_stance - c_src  # remainder ~88mm

        # Header row
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(230, 235, 245)
        pdf.set_text_color(60, 60, 60)
        pdf.set_x(pdf.l_margin)
        pdf.cell(c_id,     6, "ID",     fill=True)
        pdf.cell(c_stance, 6, "Stance", fill=True)
        pdf.cell(c_src,    6, "Source", fill=True)
        pdf.cell(c_title,  6, "Title",  fill=True)
        pdf.ln()

        # Data rows
        pdf.set_font("Arial", size=7)
        for doc in evidence_pool[:40]:
            sid    = safe(doc.get("source_id", ""))
            stance = safe(doc.get("stance", "neutral"))
            src    = safe(doc.get("metadata", {}).get("source_name", ""))[:24]
            title  = safe(doc.get("metadata", {}).get("title",  ""))[:55]
            url    = safe(doc.get("url", ""))

            pdf.set_text_color(50, 50, 50)
            pdf.set_x(pdf.l_margin)
            pdf.cell(c_id,     5, sid)
            pdf.cell(c_stance, 5, stance)
            pdf.cell(c_src,    5, src)
            pdf.cell(c_title,  5, title)
            pdf.ln()

            if url:
                pdf.set_font("Arial", "I", 6)
                pdf.set_text_color(50, 100, 200)
                pdf.set_x(pdf.l_margin + c_id)
                pdf.cell(W - c_id, 4, url[:100])
                pdf.ln()
                pdf.set_font("Arial", size=7)
                pdf.set_text_color(50, 50, 50)

    # ── Friction points ───────────────────────────────────────────────────
    valid_claims = [c for c in claims if c.get("friction_point") and c.get("consensus_claim")]
    if valid_claims:
        pdf.add_page()
        section_title(pdf, "Friction Points")
        for i, c in enumerate(valid_claims, 1):
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Arial", "B", 9)
            pdf.set_text_color(30, 30, 30)
            pdf.multi_cell(W, 6, safe(f"{i}. {c.get('friction_point','')}"))

            pdf.set_x(pdf.l_margin)
            pdf.set_font("Arial", size=8)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(W, 5, safe(f"Mainstream:  {c.get('consensus_claim','')}"))

            contrarian_text = c.get("contrarian_evidence","").strip() or "No direct contrarian evidence in sources."
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(W, 5, safe(f"Contrarian:  {contrarian_text}"))

            src_url = c.get("url","")
            if src_url:
                pdf.set_x(pdf.l_margin)
                pdf.set_text_color(50, 100, 200)
                pdf.multi_cell(W, 5, safe(f"Source: {src_url}"))
            pdf.set_text_color(50, 50, 50)
            pdf.ln(3)

    out = pdf.output(dest="S")
    return bytes(out) if isinstance(out, bytearray) else out


# ── Sidebar ───────────────────────────────────────────────────────────────────
# CHANGELOG Issue 5: removed "Source Traceability Active" info box.
with st.sidebar:
    st.title("🕵️ Investigation Stats")
    retrieval_ph = st.empty()
    inference_ph = st.empty()
    st.divider()
    retrieval_ph.metric("Sources Found", "0")
    inference_ph.metric("Friction Points", "0")
    if DEV_MODE:
        st.warning("⚙️ Developer Mode ON")


# ── Main UI ───────────────────────────────────────────────────────────────────
st.title("⚖️ Agentic-Contrarian")
st.markdown("### *Production-Grade Research Validation Infrastructure*")

query = st.text_input(
    "Analysis Topic:",
    placeholder="e.g. central bank interest rate cuts impact on inflation",
)

if st.button("Launch Deep-Dive Investigation"):
    if not query:
        st.warning("Please enter a topic to analyze.")
    else:
        start_overall = time.time()

        with st.status("🏗️ Orchestrating LangGraph Multi-Agent System...", expanded=True) as status:
            st.write("🔍 **Researcher Node:** Mining OpenSearch index across query variants...")
            time.sleep(0.5)
            st.write("🛡️ **Auditor Node:** Classifying stances and extracting friction points...")
            time.sleep(0.5)
            st.write("👁️ **Perspective Analyst:** Identifying editorial blind spots...")
            time.sleep(0.5)
            st.write("🧠 **Contrarian Node:** Synthesising dissent via Llama 3.2...")

            try:
                resp = requests.post(
                    f"http://localhost:8000/investigate?query={query}",
                    timeout=300,
                )

                if resp.status_code != 200:
                    st.error(f"Backend Error {resp.status_code}: {resp.text}")
                else:
                    final_state   = resp.json()
                    total_time    = round(time.time() - start_overall, 2)
                    evidence_pool = final_state.get("evidence_pool", [])
                    claims        = final_state.get("claims", [])
                    url_map       = build_url_map(evidence_pool)

                    retrieval_ph.metric("Sources Found",   len(evidence_pool))
                    inference_ph.metric("Friction Points", len(claims))

                    status.update(
                        label=f"✅ Investigation Complete in {total_time}s",
                        state="complete", expanded=False,
                    )

                    # CHANGELOG Issue 4: show Debug tab only in dev mode
                    tab_labels = ["📄 Executive Analysis", "🔗 Evidence Mapping", "📤 Export"]
                    if DEV_MODE:
                        tab_labels.append("⚙️ Debug")

                    tabs = st.tabs(tab_labels)
                    tab1 = tabs[0]
                    tab2 = tabs[1]
                    tab3 = tabs[2]
                    tab4 = tabs[3] if DEV_MODE else None

                    # ── Tab 1: Report with clickable citations ────────────
                    with tab1:
                        st.subheader("The Contrarian Synthesis")
                        report_md   = final_state.get("final_report", "No report generated.")
                        report_html = linkify_report(report_md, url_map)
                        st.markdown(
                            f'<div class="response-box">{report_html}</div>',
                            unsafe_allow_html=True,
                        )
                        if url_map:
                            with st.expander("📎 Source index"):
                                for sid, info in url_map.items():
                                    url = info.get("url", "")
                                    src = info.get("source", sid)
                                    ttl = info.get("title", "")
                                    if url:
                                        st.markdown(f"**{sid}** · {src} — [{ttl[:80]}]({url})")
                                    else:
                                        st.markdown(f"**{sid}** · {src} — {ttl[:80]}")

                    # ── Tab 2: Evidence Mapping ───────────────────────────
                    with tab2:
                        st.subheader("🔗 Evidence Mapping")
                        st.caption(
                            "All on-topic articles retrieved and ranked by the pipeline. "
                            "Stance is auto-classified. Click any title to read the source."
                        )

                        if not evidence_pool:
                            st.warning("No evidence retrieved. Run `python ingest.py` first.")
                        else:
                            all_stances = sorted({d.get("stance", "neutral") for d in evidence_pool})
                            selected = st.multiselect(
                                "Filter by stance:", all_stances, default=all_stances,
                                key="stance_filter",
                            )
                            filtered = [d for d in evidence_pool if d.get("stance", "neutral") in selected]
                            st.caption(f"Showing {len(filtered)} of {len(evidence_pool)} articles")

                            for doc in filtered:
                                sid      = doc.get("source_id", "")
                                stance   = doc.get("stance", "neutral")
                                category = doc.get("source_category", "")
                                meta     = doc.get("metadata", {})
                                title    = meta.get("title", "(no title)")
                                source   = meta.get("source_name", "")
                                pub      = meta.get("published_at", "")[:10]
                                url      = doc.get("url", "")
                                snippet  = doc.get("content", "")[:200]

                                badge_html = stance_badge(stance)
                                with st.expander(
                                    f"{sid}  |  {title[:70]}{'…' if len(title) > 70 else ''}",
                                    expanded=False,
                                ):
                                    st.markdown(
                                        f"{badge_html} &nbsp; **{source}** &nbsp;·&nbsp; "
                                        f"`{category}` &nbsp;·&nbsp; {pub}",
                                        unsafe_allow_html=True,
                                    )
                                    st.markdown(f"_{snippet}…_")
                                    if url:
                                        st.markdown(f"🔗 [Read full article]({url})")
                                    else:
                                        st.caption("URL unavailable")

                        st.divider()
                        st.subheader("⚡ Friction Points")
                        st.caption("Mainstream vs contrarian tensions extracted by the Auditor Node.")

                        valid_claims = [c for c in claims if c.get("friction_point") and c.get("consensus_claim")]
                        if not valid_claims:
                            st.info(
                                "No friction points extracted. "
                                "Insufficient contrarian coverage in the index for this query, "
                                "or all sources agreed."
                            )
                        else:
                            for claim in valid_claims:
                                friction   = claim.get("friction_point", "")
                                consensus  = claim.get("consensus_claim", "")
                                contrarian = claim.get("contrarian_evidence", "").strip()
                                src_id     = claim.get("source_id", "")
                                src_url    = claim.get("url", "") or url_map.get(src_id, {}).get("url", "")
                                stance     = claim.get("stance", "neutral")

                                # Auditor post-processing guarantees this is filled.
                                # Safety net only — should not normally trigger.
                                if not contrarian:
                                    contrarian = "See evidence pool for skeptical sources on this topic."

                                st.markdown(f"### {friction} {stance_badge(stance)}", unsafe_allow_html=True)
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.markdown("**📉 Mainstream Consensus**")
                                    st.info(consensus)
                                with col2:
                                    st.markdown("**🚀 Contrarian Signal**")
                                    st.success(contrarian)

                                if src_url and src_url != "URL_HERE":
                                    st.markdown(f"🔗 Primary source: [{src_id}]({src_url})")
                                else:
                                    st.caption(f"Source: {src_id} (URL unavailable)")
                                st.divider()

                    # ── Tab 3: Export (PDF download) ──────────────────────
                    # CHANGELOG Issue 3: replaced raw UUID share URL with a
                    # downloadable PDF containing the full report, evidence
                    # table, and friction points — human-readable offline.
                    with tab3:
                        st.subheader("📤 Export Report")
                        st.markdown(
                            "Download a complete PDF briefing containing the executive analysis, "
                            "full evidence table with source URLs, and all friction points."
                        )

                        report_md = final_state.get("final_report", "No report generated.")
                        pdf_bytes = create_pdf(report_md, query, evidence_pool, claims)
                        ts        = int(time.time())
                        safe_name = re.sub(r'[^\w\s-]', '', query)[:40].strip().replace(" ", "_")

                        st.download_button(
                            label="📥 Download Full PDF Briefing",
                            data=pdf_bytes,
                            file_name=f"Contrarian_{safe_name}_{ts}.pdf",
                            mime="application/pdf",
                            key="pdf_export_tab",
                            use_container_width=True,
                        )
                        st.caption(
                            f"Report ID: `{final_state.get('report_id', 'n/a')}` — "
                            "use this to retrieve raw JSON from the API: "
                            f"`GET /report/{{report_id}}`"
                        )

                    # ── Tab 4: Debug (dev mode only) ──────────────────────
                    if DEV_MODE and tab4 is not None:
                        with tab4:
                            st.subheader("⚙️ Technical State Trace")
                            st.caption(
                                "Visible because DEV_MODE=1 is set. "
                                "Remove it before deploying."
                            )
                            st.json(final_state)

            except Exception as e:
                st.error(f"❌ Investigation Failed: {e}")
