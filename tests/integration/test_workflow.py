import pytest
from margre.workflow.orchestrator import app as graph_app
from margre.workflow.state import OrchestratorState

# Mock thread for local POC
config = {"configurable": {"thread_id": "test_workflow_run"}}

@pytest.mark.asyncio
async def test_workflow_end_to_end_basics(mock_config):
    """
    Checks that the graph completes the planner and researcher nodes.
    We use the real LLM (integration mode) but we'll try to keep it simple.
    """
    query = "Research the main figures of the scientific revolution."
    
    initial_state = {
        "query": query,
        "messages": [],
        "plan": None,
        "agent_results": [],
        "current_loop": 1,
        "user_approved_plan": True # Set to True to skip HITL logic if needed for test
    }
    
    # We use a simple query to ensure the planner produces at least one task
    try:
        # Using a list to collect results from stream for inspection
        steps = []
        async for step in graph_app.astream(initial_state, config):
            steps.append(step)
            # Check for failure in node responses
            for node_name, result in step.items():
                if "error" in result:
                    pytest.fail(f"Node {node_name} returned an error: {result['error']}")

        # Verify steps coverage
        node_names = [list(s.keys())[0] for s in steps]
        assert "planner_node" in node_names
        assert any("researcher_node" in name for name in node_names)
        
        # Verify final state properties
        # The last step should contain the cumulative state or END
        final_state = steps[-1]
        
    except Exception as e:
        pytest.fail(f"Workflow integration test failed with exception: {e}")

@pytest.mark.asyncio
async def test_planner_plan_structure(mock_config):
    """Specific test for the planner's output schema."""
    from margre.workflow.planner import planner_node
    
    state = {"query": "Isaac Newton and the Principia", "messages": [], "plan": None}
    result = planner_node(state)
    
    assert "plan" in result
    plan = result["plan"]
    assert plan.subtasks
    assert any(sub.entity_name.lower().find("newton") != -1 for sub in plan.subtasks)
