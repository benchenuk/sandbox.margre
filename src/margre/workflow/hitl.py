"""Human-in-the-loop interruption mechanism."""

import logging
from typing import Literal
from margre.workflow.state import OrchestratorState

logger = logging.getLogger(__name__)

def hitl_review_plan(state: OrchestratorState) -> Literal["researcher", "planner"]:
    """
    Decides the next node after Planner based on user input.
    In LangGraph, you stop executing via `interrupt` or by pausing at this node's exit boundary.
    Here we check `user_approved_plan`. If False, we stay blocked (handled via LangGraph `interruptBefore` or manual logic in CLI).
    If the CLI allows modification, the `plan` in state may be mutated before resuming.
    """
    if state.get("user_approved_plan", False):
        return "researcher"
    else:
        # Request a new plan or loop back if rejected
        logger.info("Plan not approved. Returning to planner (or handle appropriately).")
        return "planner"
