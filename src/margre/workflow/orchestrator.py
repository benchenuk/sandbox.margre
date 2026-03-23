"""Top-level LangGraph orchestrator graph."""

import uuid
import logging
from typing import Literal, ContextManager, Generator
from contextlib import contextmanager

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send

from margre.workflow.state import OrchestratorState, ResearcherState, SubTask
from margre.workflow.planner import planner_node
from margre.workflow.researcher import researcher_node
from margre.workflow.aggregator import aggregator_node

logger = logging.getLogger(__name__)

# Helper to provide persistent checkpointer
@contextmanager
def get_checkpointer() -> Generator[SqliteSaver, None, None]:
    """Provides a managed sqlite checkpointer."""
    from margre.persistence.notes import get_runs_dir
    db_path = get_runs_dir() / "checkpoints.db"
    # Create parent dirs if needed
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        yield saver

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
        
    # Reuse run_id if already present (important for resumes)
    # Actually OrchestratorState doesn't have run_id, but the Researchers do.
    # We should probably put run_id in OrchestratorState if we want persistence.
    # For now, we'll generate one if not found in any message/metadata (SIMPLIFIED)
    run_id = str(uuid.uuid4())[:8]
    logger.info(f"ORCHESTRATOR: Starting/Resuming research run with ID: {run_id}")
    
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
        
    logger.info(f"ORCHESTRATOR: Dispatching {len(sends)} research agents.")
    return sends

def route_after_planner(state: OrchestratorState) -> Literal["researcher_dispatch", "planner"]:
    """
    Decides the path after the planner node.
    """
    if state.get("user_approved_plan", False):
        logger.info("ORCHESTRATOR: Plan approved, proceeding to research dispatch.")
        return "researcher_dispatch"
    
    # If a plan exists, we have reached the interrupt point for approval
    if state.get("plan"):
        logger.info("ORCHESTRATOR: Plan generated, awaiting HITL approval.")
        return "researcher_dispatch"
    
    logger.warning("ORCHESTRATOR: No plan available, returning to planner.")
    return "planner"

def route_after_aggregation(state: OrchestratorState) -> Literal["refine", "end"]:
    """
    Decides whether to loop back for refinement or end the workflow.
    """
    from margre.config import get_config
    config = get_config()
    
    # Check loop limit
    loop_count = state.get("loop_count", 0)
    if loop_count >= config.workflow.max_research_loops:
        logger.info(f"ORCHESTRATOR: Loop limit ({config.workflow.max_research_loops}) reached. Ending.")
        return "end"
    
    # For POC, if gaps found, we loop. 
    # In a full HITL, this would follow a user_approved_refinement flag.
    if state.get("suggested_gaps"):
        logger.info(f"ORCHESTRATOR: Gaps found in loop {loop_count}. Proposing refinement.")
        return "refine"
    
    return "end"

#
# Define the Graph
#
def create_graph(checkpointer: SqliteSaver | None = None):
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(OrchestratorState)
    
    # 1. Add Nodes
    workflow.add_node("planner_node", planner_node)
    workflow.add_node("researcher_node", researcher_node)
    workflow.add_node("aggregator_node", aggregator_node)
    
    def research_dispatch_node(state: OrchestratorState) -> dict:
        return {}
    workflow.add_node("research_dispatch_node", research_dispatch_node)
    
    # 2. Add Edges
    workflow.add_edge(START, "planner_node")
    
    workflow.add_conditional_edges(
        "planner_node",
        route_after_planner,
        {
            "researcher_dispatch": "research_dispatch_node",
            "planner": "planner_node"
        }
    )
    
    workflow.add_conditional_edges(
        "research_dispatch_node",
        continue_to_researchers,
        ["researcher_node"]
    )
    
    workflow.add_edge("researcher_node", "aggregator_node")
    
    workflow.add_conditional_edges(
        "aggregator_node",
        route_after_aggregation,
        {
            "refine": "planner_node",
            "end": END
        }
    )
    
    # Compile with checkpointer and HITL interrupts
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=["planner_node", "aggregator_node"]
    )
