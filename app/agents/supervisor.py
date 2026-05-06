from langgraph.graph import StateGraph, END
from langchain_ollama import ChatOllama
from typing import TypedDict, List

# --- 1. Initialize the LLM ---
llm = ChatOllama(model="llama3.2", temperature=0.7)

class AgentState(TypedDict):
    query: str
    context: List[str]
    response: str  # This is what the API is now looking for
    audited: bool

def research_node(state: AgentState):
    # Retrieve data, then return the state UPDATED with context
    # Use state.get() to safely access the query
    context = ["Retrieved context from OpenSearch archive"]
    return {**state, "context": context}

def auditor_node(state: AgentState):
    # Pass through everything and add the audit flag
    return {**state, "audited": True}

def contrarian_node(state: AgentState):
    # Now state['query'] is guaranteed to be preserved
    user_query = state.get('query', 'No query provided')
    context_data = state.get('context', [])
    
    prompt = f"""
    You are a Contrarian Analyst. Based on this context: {context_data}
    Provide a unique, non-consensus view on the user query: {user_query}
    """
    res = llm.invoke(prompt)
    return {**state, "response": res.content}

workflow = StateGraph(AgentState)
workflow.add_node("researcher", research_node)
workflow.add_node("auditor", auditor_node)
workflow.add_node("contrarian", contrarian_node) # Add the node

workflow.set_entry_point("researcher")
workflow.add_edge("researcher", "auditor")
workflow.add_edge("auditor", "contrarian") # Link to the new node
workflow.add_edge("contrarian", END)

app = workflow.compile()