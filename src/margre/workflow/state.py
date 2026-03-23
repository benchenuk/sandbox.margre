"""State schemas for LangGraph workflows."""

import operator
from typing import Annotated, Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage

#
# Discovery Schema
#
class DiscoveryTask(BaseModel):
    """A connection-oriented research subtask."""
    target_person: str = Field(description="Name of the person being researched")
    search_angle: str = Field(description="The perspective (collaborators, critics, institutions, influence)")
    research_query: str = Field(description="Specific research question or query to pursue")

class DiscoveryPlan(BaseModel):
    """A collection of tasks to discover connections for a seed person."""
    seed_person: str = Field(description="Current focal person")
    subtasks: List[DiscoveryTask] = Field(description="Connection-oriented discovery tasks")

#
# Overall Graph State
#
class OrchestratorState(TypedDict):
    """The state of the top-level discovery workflow."""
    seed_person: str
    messages: Annotated[list[BaseMessage], operator.add]
    plan: Optional[DiscoveryPlan]
    
    # Track results from sub-agents
    agent_results: Annotated[List[Dict[str, Any]], operator.add]
    
    # Discovery tracking
    discovered_persons: Annotated[List[str], operator.add]
    loop_count: int
    user_approved_plan: bool
    
    # Master results (High-level overview + expansion candidates)
    master_report: Optional[str]
    suggested_gaps: List[str] 

#
# Sub-Agent State
#
class ResearcherState(TypedDict):
    """State for an individual discovery sub-agent."""
    run_id: str
    agent_id: str
    subtask: DiscoveryTask
    
    # Internal messaging for the subagent LLM reasoning
    messages: Annotated[list[BaseMessage], operator.add]
    
    # Results
    final_report: str
    structured_data: Dict[str, Any]
