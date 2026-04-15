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

class DiscoveredRelationship(BaseModel):
    """A single relational connection extracted from research."""
    rel_type: str = Field(description="Relationship label (e.g., KNEW, COLLABORATED_WITH, STUDIED_AT)")
    target_name: str = Field(description="Name of the other person, institution, contribution, event, or location")
    target_label: str = Field(description="Type of the target entity (Person, Institution, Contribution, Location, Event)")
    context: str = Field(description="Brief historical context of the connection")
    year: Optional[int] = Field(None, description="The most relevant year for timeline ordering")
    date: Optional[str] = Field(None, description="Specific known date (e.g., DoB, death date)")
    period: Optional[str] = Field(None, description="Human readable period or date range")

class DiscoveryExtractionResult(BaseModel):
    """Structured collection of all discovered connections."""
    relationships: List[DiscoveredRelationship] = Field(default_factory=list)
    new_persons: List[str] = Field(default_factory=list, description="List of NAMES of and only of individuals for potential further research")

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

    # HITL revision loop
    plan_revision_count: int
    plan_revision_comments: Optional[str]
    
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
