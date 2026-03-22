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
        logger.error("ORCHESTRATOR: No plan or subtasks found, terminating flow.")
        return []
        
    # Generate unique run_id if not present
    run_id = str(uuid.uuid4())[:8]
    logger.info(f"ORCHESTRATOR: Starting new research run with ID: {run_id}")
    
    # Spawn one node per subtask
    sends = []
    for idx, task in enumerate(plan.subtasks):
        agent_id = f"agent_{idx}_{task.entity_name.lower().replace(' ', '_')}"
        
        logger.debug(f"ORCHESTRATOR: Preparing state for {agent_id} (Task: {task.entity_name})")
        
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
        
    logger.info(f"ORCHESTRATOR: Dispatching {len(sends)} research agents for run {run_id}.")
    return sends

def route_after_planner(state: OrchestratorState) -> Literal["researcher_dispatch", "planner"]:
    """
    Decides the path after the planner node.
    """
    if state.get("user_approved_plan", False):
        logger.info("ORCHESTRATOR: Plan approved, proceeding to research dispatch.")
        return "researcher_dispatch"
    
    if state.get("plan"):
        logger.info("ORCHESTRATOR: Plan generated, awaiting approval.")
        return "researcher_dispatch"
    
    logger.warning("ORCHESTRATOR: No plan available, returning to planner.")
    return "planner"

#
# Routing logic for Refinement
#
def route_after_aggregation(state: OrchestratorState) -> Literal["refine", "end"]:
    """
    Decides whether to loop back for refinement or end the workflow.
    This is intended to be a HITL point or an automated heuristic.
    For Phase 5, if 'suggested_gaps' exist and we haven't hit loop limit, check HITL.
    """
    from margre.config import get_config
    config = get_config()
    
    # Check loop limit
    if state.get("loop_count", 0) >= config.workflow.max_research_loops:
        logger.info(f"ORCHESTRATOR: Loop limit ({config.workflow.max_research_loops}) reached. Ending.")
        return "end"
    
    # In a full HITL system, we would interrupt here to show the report and ask the user.
    # For and automated POC or until we add the CLI interrupt, we can terminate or auto-refine.
    # We will favor terminating unless the user explicitly requested a resume/refine in the future.
    return "end"

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
    
    # Jump node for Send logic
    def research_dispatch_node(state: OrchestratorState) -> dict:
        return {}
    workflow.add_node("research_dispatch_node", research_dispatch_node)
    
    # 2. Add Edges
    workflow.add_edge(START, "planner_node")
    
    # Planner -> HITL Approval -> Dispatch
    workflow.add_conditional_edges(
        "planner_node",
        route_after_planner,
        {
            "researcher_dispatch": "research_dispatch_node",
            "planner": "planner_node"
        }
    )
    
    # Dispatch -> Send researchers
    workflow.add_conditional_edges(
        "research_dispatch_node",
        continue_to_researchers,
        ["researcher_node"]
    )
    
    # Researcher results flow into aggregator
    workflow.add_edge("researcher_node", "aggregator_node")
    
    # Aggregator -> Refinement Loop check
    workflow.add_conditional_edges(
        "aggregator_node",
        route_after_aggregation,
        {
            "refine": "planner_node",
            "end": END
        }
    )
    
    return workflow.compile()

# Generate the app
app = create_graph()
