"""Researcher sub-agent node implementation."""

import logging
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from margre.workflow.state import ResearcherState
from margre.llm.client import get_model
from margre.search import get_search_provider
from margre.persistence.notes import save_research_note
from margre.persistence.runs import save_agent_structured_result
from margre.graph.repository import save_entity, save_source, link_entity_to_source
from margre.llm.prompts import (
    RESEARCHER_SYNTHESIS_SYSTEM_PROMPT,
    RESEARCHER_SYNTHESIS_HUMAN_TEMPLATE,
    RESEARCHER_EXTRACTION_SYSTEM_PROMPT
)

logger = logging.getLogger(__name__)

#
# Schema for structured entity extraction from research results
#
class EntityProperties(BaseModel):
    """Properties for a single historical entity."""
    description: str = Field(description="Brief summary of the entity's significance")
    key_dates: List[str] = Field(default_factory=list, description="Important historical dates (e.g., years of birth/death, dates of events)")
    properties: Dict[str, str] = Field(default_factory=dict, description="Arbitrary key-value pairs (e.g., nationality, role, etc.)")

class StructuredResearchSummary(BaseModel):
    """Structured extraction of entities and relationships from research text."""
    entities: List[Dict[str, Any]] = Field(description="List of entities found, where each has 'name', 'label', and 'properties' (matching EntityProperties)")

def researcher_node(state: ResearcherState) -> dict:
    """
    Executes a single research subtask.
    1. Web Search
    2. Synthesis (Markdown)
    3. Structured Extraction
    4. Persistence (Filesystem + Neo4j)
    """
    subtask = state["subtask"]
    agent_id = state["agent_id"]
    run_id = state["run_id"]
    
    logger.info(f"RESEARCHER [{agent_id}]: Starting subtask: {subtask.entity_name} ({subtask.entity_type})")
    
    # 1. Search
    provider = get_search_provider()
    logger.info(f"RESEARCHER [{agent_id}]: Executing web search for: '{subtask.research_query}'")
    search_results = provider.search(subtask.research_query, max_results=5)
    
    if not search_results:
        logger.warning(f"RESEARCHER [{agent_id}]: No search results found for query: '{subtask.research_query}'")
        return {
            "final_report": f"No information found for {subtask.entity_name}.",
            "structured_data": {}
        }

    logger.info(f"RESEARCHER [{agent_id}]: Found {len(search_results)} search results.")
    for idx, r in enumerate(search_results):
        logger.debug(f"RESEARCHER [{agent_id}]: Result {idx+1}: {r.title} ({r.url})")

    # 2. Synthesis (Markdown Report)
    model = get_model()
    sources_text = "\n\n".join([f"Source: {r.url}\nTitle: {r.title}\nSnippet: {r.snippet}" for r in search_results])
    
    synthesis_prompt = [
        SystemMessage(content=RESEARCHER_SYNTHESIS_SYSTEM_PROMPT),
        HumanMessage(content=RESEARCHER_SYNTHESIS_HUMAN_TEMPLATE.format(
            query=subtask.research_query,
            entity_name=subtask.entity_name,
            entity_type=subtask.entity_type,
            snippets=sources_text
        ))
    ]
    
    logger.debug(f"RESEARCHER [{agent_id}]: Sending synthesis prompt to LLM.")
    report_res = model.invoke(synthesis_prompt)
    report = report_res.content
    logger.info(f"RESEARCHER [{agent_id}]: Synthesis complete. Report length: {len(report)} characters.")
    
    # 3. Save to Filesystem (Markdown)
    report_path = save_research_note(run_id, agent_id, report)
    logger.info(f"RESEARCHER [{agent_id}]: Saved Markdown report to: {report_path}")

    # 4. Structured Extraction
    extraction_prompt = [
        SystemMessage(content=RESEARCHER_EXTRACTION_SYSTEM_PROMPT),
        HumanMessage(content=f"Research Report:\n{report}")
    ]
    
    logger.info(f"RESEARCHER [{agent_id}]: Extracting structured entities from report.")
    structured_model = model.with_structured_output(schema=StructuredResearchSummary)
    extracted: StructuredResearchSummary = structured_model.invoke(extraction_prompt)
    
    # 5. Save to Persistance (Neo4j + JSON)
    json_path = save_agent_structured_result(run_id, agent_id, extracted.model_dump())
    logger.debug(f"RESEARCHER [{agent_id}]: Saved structured JSON to: {json_path}")
    
    entities_count = 0
    # Save the source nodes first
    for r in search_results:
        save_source(r.url, r.title, r.snippet, file_path=report_path)

    # Save entities and link them to sources (simplification: link to all primary sources)
    for ent in extracted.entities:
        label = ent.get("label", "Person")
        name = ent.get("name", "")
        props = ent.get("properties", {}) or {}
        
        if not name:
            continue
            
        if hasattr(props, "model_dump"):
            props = props.model_dump()
        
        if save_entity(label, {"name": name, **props}):
            entities_count += 1
            if search_results:
                link_entity_to_source(name, label, search_results[0].url)

    logger.info(f"RESEARCHER [{agent_id}]: Persisted {entities_count} entities to Neo4j.")

    return {
        "final_report": report,
        "structured_data": extracted.model_dump(),
        "agent_results": [{
            "agent_id": agent_id,
            "entity_name": subtask.entity_name,
            "report_path": report_path,
            "entities_count": entities_count
        }]
    }

