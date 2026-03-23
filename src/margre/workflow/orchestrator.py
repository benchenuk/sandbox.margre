"""Top-level LangGraph orchestrator graph."""

import uuid
import logging
from typing import Literal, ContextManager, Generator
from contextlib import contextmanager

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send

from margre.workflow.state import OrchestratorState, ResearcherState
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
        logger.error("ORCHESTRATOR: No discovery plan found, terminating flow.")
        return []
        
    # Generate run_id from seed_person if not provided internally 
    # (Actually we should probably pass it in the thread config, but keeping it simple for now)
    run_id = str(uuid.uuid4())[:8] 
    
    # Spawn one node per subtask
    sends = []
    for idx, task in enumerate(plan.subtasks):
        agent_id = f"agent_{idx}_{task.target_person.lower().replace(' ', '_')}"
        
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
        
    logger.info(f"ORCHESTRATOR: Dispatching {len(sends)} discovery agents for '{plan.seed_person}'.")
    return sends

def route_after_planner(state: OrchestratorState) -> Literal["researcher_dispatch", "planner"]:
    """
    Decides the path after the planner node.
    """
    if state.get("user_approved_plan", False):
        logger.info("ORCHESTRATOR: Plan approved, proceeding to discovery.")
        return "researcher_dispatch"
    
    # HITL Interrupt point
    if state.get("plan"):
        return "researcher_dispatch"
    
    return "planner"

def route_after_aggregation(state: OrchestratorState) -> Literal["expand", "end"]:
    """
    Decides whether to expand to New Persons or end the workflow.
    """
    from margre.config import get_config
    config = get_config()
    
    loop_count = state.get("loop_count", 0)
    
    # 1. Depth Check
    if loop_count >= config.workflow.max_expansion_depth:
        logger.info(f"ORCHESTRATOR: Expansion depth limit ({config.workflow.max_expansion_depth}) reached.")
        return "end"
    
    # 2. Candidate Check
    if not state.get("suggested_gaps"):
        logger.info("ORCHESTRATOR: No new expansion candidates found. Ending.")
        return "end"
    
    # 3. Expansion Logic
    # In next loop, we will pick candidates from suggested_gaps.
    # The actual HITL selection happens in the CLI before resuming.
    logger.info(f"ORCHESTRATOR: {len(state['suggested_gaps'])} candidates ready for expansion loop {loop_count + 1}.")
    return "expand"

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
            "expand": "planner_node",
            "end": END
        }
    )
    
    # Compile with checkpointer and HITL interrupts
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=["planner_node", "aggregator_node"]
    )
