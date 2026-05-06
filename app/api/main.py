from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from app.agents.supervisor import app as agent_app

api = FastAPI(title="Contrarian AI")

# app/api/main.py

@api.post("/ask")
async def ask_contrarian(query: str):
    # Pass the query into the graph
    final_state = agent_app.invoke({"query": query})
    
    # FIX: Access 'response' instead of 'messages'
    return {"response": final_state.get("response", "No response generated")}