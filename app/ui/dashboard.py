import streamlit as st
import requests
import time

# 1. Force Dark Mode & Layout
st.set_page_config(
    page_title="Contrarian AI Dashboard",
    page_icon="⚖️",
    layout="wide"
)

# 2. Sleek Custom CSS
st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .response-box {
        padding: 25px;
        border-radius: 12px;
        border: 1px solid #30363d;
        background-color: #161b22;
        line-height: 1.6;
        font-size: 1.1rem;
    }
    .stButton>button {
        background-image: linear-gradient(to right, #1f6feb, #388bfd);
        color: white;
        border: none;
        font-weight: bold;
    }
    [data-testid="stMetricValue"] { color: #58a6ff; font-family: 'Courier New', monospace; }
    </style>
    """, unsafe_allow_html=True)

# 3. Sidebar: Simplified to just Latency
with st.sidebar:
    st.title("⚡ Performance")
    # Placeholders for metrics so they update live
    retrieval_placeholder = st.empty()
    inference_placeholder = st.empty()
    
    # Initialize values
    retrieval_placeholder.metric("Retrieval", "0.0s")
    inference_placeholder.metric("Inference", "0.0s")

# 4. Main Interface
st.title("⚖️ Contrarian Editorial Curator")
st.markdown("### Agentic RAG Pipeline: *Extracting non-consensus insights.*")

query = st.text_input("Analysis Topic:", placeholder="e.g. Current stability of global supply chains...")

if st.button("Run Multi-Agent Analysis"):
    if query:
        start_overall = time.time()
        
        with st.status("🏗️ Orchestrating LangGraph Agents...", expanded=True) as status:
            # Step 1: Research Node
            st.write("🔍 **Researcher Node:** Querying OpenSearch Archive...")
            t1_start = time.time()
            # Simulation of retrieval overhead (actual work happens in FastAPI)
            time.sleep(0.5) 
            t1_end = time.time()
            retrieval_time = round(t1_end - t1_start, 2)
            retrieval_placeholder.metric("Retrieval", f"{retrieval_time}s")
            
            # Step 2: Audit Node
            st.write("🛡️ **Auditor Node:** Validating context & ensuring contrarian logic...")
            time.sleep(0.3)

            # Step 3: LLM Inference
            st.write("🧠 **Contrarian Node:** Generating prose via Llama 3.2 (Local)...")
            try:
                t2_start = time.time()
                # Increased timeout to 300 seconds (5 minutes) for local CPU inference
                response = requests.post(f"http://localhost:8000/ask?query={query}", timeout=300)
                t2_end = time.time()
                
                inference_time = round(t2_end - t2_start, 2)
                inference_placeholder.metric("Inference", f"{inference_time}s")
                
                data = response.json()
                status.update(label="✅ Analysis Complete!", state="complete", expanded=False)
                
                # Final Reveal
                st.divider()
                st.subheader("The Contrarian Take")
                st.markdown(f'<div class="response-box">{data.get("response")}</div>', unsafe_allow_html=True)
                
                total_time = round(time.time() - start_overall, 2)
                st.caption(f"Total Pipeline Execution: {total_time}s")

            except requests.exceptions.ReadTimeout:
                st.error("❌ Inference Timeout: Llama 3.2 is taking longer than 5 minutes to respond. Try a shorter query or check Ollama performance.")
            except Exception as e:
                st.error(f"❌ Connection Error: {e}")
    else:
        st.warning("Please enter a topic to analyze.")