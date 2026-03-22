"""Aggregator node for synthesizing multiple research reports."""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from margre.llm.client import get_model
from margre.workflow.state import OrchestratorState
from margre.llm.prompts import AGGREGATOR_SYSTEM_PROMPT
from margre.persistence.runs import save_run_metadata

logger = logging.getLogger(__name__)

def aggregator_node(state: OrchestratorState) -> dict:
    """
    Synthesizes results from all research agents into a master report.
    """
    logger.info(f"Aggregating results from {len(state['agent_results'])} agents.")
    
    if not state["agent_results"]:
        return {"messages": [SystemMessage(content="No research results to aggregate.")]}
        
    model = get_model()
    
    # Collect all reports into a single context
    context_chunks = []
    for res in state["agent_results"]:
        agent_id = res.get("agent_id", "Unknown")
        entity = res.get("entity_name", "Unknown")
        report_path = res.get("report_path", "")
        
        # Read the report from disk
        try:
            from margre.persistence.notes import read_research_note
            # We need the run_id from one of the results
            run_id = report_path.split("/")[-3] # /runs/<run_id>/agents/<agent_id>.md
            content = read_research_note(run_id, agent_id)
            if content:
                context_chunks.append(f"--- AGENT: {agent_id} (Entity: {entity}) ---\n{content}")
        except Exception as e:
            logger.warning(f"Could not read report for {agent_id}: {e}")

    full_context = "\n\n".join(context_chunks)
    
    prompt = [
        SystemMessage(content=AGGREGATOR_SYSTEM_PROMPT.format(topic=state["query"])),
        HumanMessage(content=f"Sub-Agent Reports:\n\n{full_context}\n\nPlease synthesize the final master report.")
    ]
    
    master_report: str = model.invoke(prompt).content
    
    # Save master report metadata
    run_id = state["agent_results"][0]["report_path"].split("/")[-3]
    save_run_metadata(run_id, {
        "query": state["query"],
        "master_report": master_report,
        "agents_involved": [r["agent_id"] for r in state["agent_results"]]
    })
    
    logger.info(f"Master report generated and saved for run: {run_id}")
    
    return {
        "messages": [HumanMessage(content="Master report synthesized.")],
        # We can store the final report in state if needed for further loops
    }
