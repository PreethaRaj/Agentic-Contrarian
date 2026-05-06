import pytest
from app.agents.supervisor import app as agent_app

@pytest.mark.asyncio
async def test_agent_workflow():
    inputs = {"query": "test query", "context": []}
    config = {"configurable": {"thread_id": "1"}}
    
    # Test if the graph can execute at least one step
    async for output in agent_app.astream(inputs, config):
        assert output is not None
        break # We just want to see it trigger