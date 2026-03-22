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
    agent_count = len(state['agent_results'])
    logger.info(f"AGGREGATOR: Starting synthesis for query '{state['query']}' using {agent_count} agent reports.")
    
    if not state["agent_results"]:
        logger.warning("AGGREGATOR: No research results available to aggregate.")
        return {"messages": [SystemMessage(content="No research results to aggregate.")]}
        
    model = get_model()
    
    # Collect all reports into a single context
    context_chunks = []
    for res in state["agent_results"]:
        agent_id = res.get("agent_id", "Unknown")
        entity = res.get("entity_name", "Unknown")
        report_path = res.get("report_path", "")
        
        logger.debug(f"AGGREGATOR: Loading report for agent '{agent_id}' (Entity: {entity}) from {report_path}")
        
        try:
            from margre.persistence.notes import read_research_note
            # /runs/<run_id>/agents/<agent_id>.md
            parts = report_path.split("/")
            run_id = parts[-3]
            content = read_research_note(run_id, agent_id)
            if content:
                context_chunks.append(f"--- AGENT: {agent_id} (Entity: {entity}) ---\n{content}")
                logger.debug(f"AGGREGATOR: Successfully loaded {len(content)} characters from {agent_id}.")
            else:
                logger.warning(f"AGGREGATOR: Report for {agent_id} was empty.")
        except Exception as e:
            logger.warning(f"AGGREGATOR: Could not read report for {agent_id}: {e}")

    full_context = "\n\n".join(context_chunks)
    logger.debug(f"AGGREGATOR: Combined context length: {len(full_context)} characters.")
    
    prompt = [
        SystemMessage(content=AGGREGATOR_SYSTEM_PROMPT.format(topic=state["query"])),
        HumanMessage(content=f"Sub-Agent Reports:\n\n{full_context}\n\nPlease synthesize the final master report.")
    ]
    
    logger.info("AGGREGATOR: Invoking LLM for master report synthesis...")
    master_report_res = model.invoke(prompt)
    master_report = master_report_res.content
    logger.info(f"AGGREGATOR: Master report generated. Length: {len(master_report)} characters.")
    
    # Save master report metadata
    try:
        run_id = state["agent_results"][0]["report_path"].split("/")[-3]
        meta_path = save_run_metadata(run_id, {
            "query": state["query"],
            "master_report": master_report,
            "agents_involved": [r["agent_id"] for r in state["agent_results"]]
        })
        logger.info(f"AGGREGATOR: Master report and metadata saved for run: {run_id} at {meta_path}")
    except Exception as e:
        logger.error(f"AGGREGATOR: Failed to save run metadata: {e}")
    
    return {
        "messages": [HumanMessage(content="Master report synthesized.")],
    }
