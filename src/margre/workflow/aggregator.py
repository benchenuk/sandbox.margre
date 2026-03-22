"""Aggregator node for synthesizing multiple research reports."""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from margre.llm.client import get_model
from margre.workflow.state import OrchestratorState
from margre.llm.prompts import AGGREGATOR_SYSTEM_PROMPT
from margre.persistence.runs import save_run_metadata

logger = logging.getLogger(__name__)

from pydantic import BaseModel, Field
from typing import List, Optional

class AggregatedResult(BaseModel):
    """Structured synthesis output with gap analysis."""
    master_report: str = Field(description="Synthesized markdown report")
    suggested_gaps: List[str] = Field(description="2-3 specific questions or entities to research further")

def aggregator_node(state: OrchestratorState) -> dict:
    """
    Synthesizes results from all research agents into a master report and identifies gaps.
    """
    agent_count = len(state['agent_results'])
    logger.info(f"AGGREGATOR: Starting synthesis for query '{state['query']}' using {agent_count} agent reports.")
    
    if not state["agent_results"]:
        return {"messages": [SystemMessage(content="No research results to aggregate.")]}
        
    model = get_model()
    
    # Collect all reports into a single context
    context_chunks = []
    for res in state["agent_results"]:
        agent_id = res.get("agent_id", "Unknown")
        entity = res.get("entity_name", "Unknown")
        report_path = res.get("report_path", "")
        
        try:
            from margre.persistence.notes import read_research_note
            # /runs/<run_id>/agents/<agent_id>.md
            parts = report_path.split("/")
            run_id = parts[-3]
            content = read_research_note(run_id, agent_id)
            if content:
                context_chunks.append(f"--- AGENT: {agent_id} (Entity: {entity}) ---\n{content}")
        except Exception as e:
            logger.warning(f"AGGREGATOR: Could not read report for {agent_id}: {e}")

    full_context = "\n\n".join(context_chunks)
    
    prompt = [
        SystemMessage(content=AGGREGATOR_SYSTEM_PROMPT.format(topic=state["query"])),
        HumanMessage(content=f"Sub-Agent Reports:\n\n{full_context}\n\nPlease synthesize the master report and identify gaps.")
    ]
    
    # Use structured output to get summary and gaps separately
    structured_model = model.with_structured_output(schema=AggregatedResult)
    logger.info("AGGREGATOR: Performing synthesis and gap analysis...")
    result: AggregatedResult = structured_model.invoke(prompt)
    
    master_report = result.master_report
    suggested_gaps = result.suggested_gaps
    
    # Save master report metadata
    try:
        run_id = state["agent_results"][0]["report_path"].split("/")[-3]
        save_run_metadata(run_id, {
            "query": state["query"],
            "master_report": master_report,
            "suggested_gaps": suggested_gaps,
            "agents_involved": [r["agent_id"] for r in state["agent_results"]]
        })
    except Exception as e:
        logger.error(f"AGGREGATOR: Failed to save run metadata: {e}")
    
    logger.info(f"AGGREGATOR: Final synthesis complete. Found {len(suggested_gaps)} gaps.")
    
    return {
        "master_report": master_report,
        "suggested_gaps": suggested_gaps,
        "messages": [HumanMessage(content="Master report synthesized with gap analysis.")],
    }
