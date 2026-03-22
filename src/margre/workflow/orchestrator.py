"""Top-level LangGraph orchestrator graph."""

import uuid
import logging
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send

from margre.workflow.state import OrchestratorState, ResearcherState, SubTask
from margre.workflow.planner import planner_node
from margre.workflow.researcher import researcher_node
from margre.workflow.aggregator import aggregator_node

logger = logging.getLogger(__name__)

#
# Sending logic for dynamic parallel dispatch
#
def continue_to_researchers(state: OrchestratorState) -> list[Send]:
    """
    Decides how many research sub-agents to spawn based on the generated plan.
    Uses the Send API to dynamically route to 'researcher_node'.
    """
    plan = state.get("plan")
    if not plan or not plan.subtasks:
        logger.warning("No plan or subtasks found, ending workflow.")
        return []
        
    # Generate unique run_id if not present
    run_id = str(uuid.uuid4())[:8] # Simplified for POC
    
    # Spawn one node per subtask
    sends = []
    for idx, task in enumerate(plan.subtasks):
        agent_id = f"agent_{idx}_{task.entity_name.lower().replace(' ', '_')}"
        
        # Construct child state (ResearcherState)
        child_state = {
            "run_id": run_id,
            "agent_id": agent_id,
            "subtask": task,
            "messages": [],
            "final_report": "",
            "structured_data": {}
        }
        
        sends.append(Send("researcher_node", child_state))
        
    logger.info(f"Orchestrator dispatching {len(sends)} research agents.")
    return sends

#
# Routing logic for HITL
#
def route_after_planner(state: OrchestratorState) -> Literal["researcher_dispatch", "planner"]:
    """
    Decides the path after the planner node.
    Normally this would be where we check 'user_approved_plan' for the HITL loop.
    For Phase 3/POC, if a plan exists we move forward.
    """
    if state.get("user_approved_plan", False):
        return "researcher_dispatch"
    
    # If not approved, in a real HITL system we would interrupt here.
    # We will implement the actual interrupt in the CLI/TUI layer later.
    # For now, let's assume auto-approval for the basic POC if not using HITL.
    if state.get("plan"):
        return "researcher_dispatch"
    
    return "planner"

#
# Define the Graph
#
def create_graph():
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(OrchestratorState)
    
    # 1. Add Nodes
    workflow.add_node("planner_node", planner_node)
    workflow.add_node("researcher_node", researcher_node)
    workflow.add_node("aggregator_node", aggregator_node)
    
    # 2. Add Edges
    workflow.add_edge(START, "planner_node")
    
    # Conditional edge from planner to research (parallel dispatch)
    workflow.add_conditional_edges(
        "planner_node",
        route_after_planner,
        {
            "researcher_dispatch": "research_dispatch_node",
            "planner": "planner_node"
        }
    )
    
    # Dynamic send-based node for parallel research
    # We use a dummy jump node to hold the conditional logic for 'Send'
    def research_dispatch_node(state: OrchestratorState) -> dict:
        # This is a no-op logic node that triggers the Send conditional edge
        return {}
    
    workflow.add_node("research_dispatch_node", research_dispatch_node)
    
    # The actual dispatch magic
    workflow.add_conditional_edges(
        "research_dispatch_node",
        continue_to_researchers,
        ["researcher_node"]
    )
    
    # researcher nodes collect their results automatically into agent_results
    # then they flow into the aggregator junction
    workflow.add_edge("researcher_node", "aggregator_node")
    workflow.add_edge("aggregator_node", END)
    
    return workflow.compile()

# Generate the app
app = create_graph()
