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

from collections import Counter
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from typing import List, Optional

from margre.llm.client import get_model
from margre.workflow.state import OrchestratorState
from margre.llm.prompts import AGGREGATOR_SYSTEM_PROMPT
from margre.persistence.runs import save_run_metadata
from margre.config import get_config
from margre.graph.repository import person_exists

logger = logging.getLogger(__name__)

class GapAnalysisResult(BaseModel):
    """Structured gap analysis output."""
    suggested_gaps: List[str] = Field(description="2-3 specific questions or expansion candidates")

def aggregator_node(state: OrchestratorState) -> dict:
    """
    Synthesizes discovery results and identifies next expansion candidates.
    """
    seed_person = state['seed_person']
    agent_results = state.get('agent_results', [])
    logger.info(f"AGGREGATOR: Synthesizing results for: {seed_person}")
    
    if not agent_results:
        return {"messages": [SystemMessage(content="No discovery results to aggregate.")]}
        
    config = get_config()
    model = get_model()
    
    # 1. Collect all agent reports for synthesis
    context_chunks = []
    for res in agent_results:
        agent_id = res.get("agent_id")
        report_path = res.get("report_path")
        try:
            from margre.persistence.notes import read_research_note
            parts = report_path.split("/")
            run_id = parts[-3]
            content = read_research_note(run_id, agent_id)
            if content:
                context_chunks.append(f"### Discovery Report: {agent_id}\n{content}")
        except Exception as e:
            logger.warning(f"AGGREGATOR: Could not read report for {agent_id}: {e}")

    full_context = "\n\n".join(context_chunks)
    
    # 2. Synthesis (Narrative overview)
    synthesis_prompt = [
        SystemMessage(content=AGGREGATOR_SYSTEM_PROMPT.format(topic=seed_person)),
        HumanMessage(content=f"Sub-Agent Discovery Reports:\n\n{full_context}\n\nPlease synthesize a final overview of {seed_person}'s connections.")
    ]
    master_report = model.invoke(synthesis_prompt).content
 
    # 3. Expansion Candidate Filtering
    # Collect all discovered persons from all agents
    all_discovered = state.get("discovered_persons", [])
    
    # Filter out the seed person and those already in Neo4j
    candidates = [p for p in all_discovered if p.lower() != seed_person.lower()]
    
    # Simple deduplication and ranking by frequency
    counts = Counter(candidates)
    
    # Filter further: only keep those we haven't researched (not in Neo4j)
    unique_candidates = []
    for name, count in counts.most_common():
        if not person_exists(name):
            unique_candidates.append(name)
        else:
            logger.debug(f"AGGREGATOR: Skipping {name} (already in graph).")

    # 4. Limit and Log
    limit = config.workflow.max_candidates_per_loop
    final_candidates = unique_candidates[:limit]
    dropped = unique_candidates[limit:]
    
    if dropped:
        logger.info(f"AGGREGATOR: Dropped {len(dropped)} candidates due to limit ({limit}): {', '.join(dropped)}")
    
    logger.info(f"AGGREGATOR: Identified {len(final_candidates)} expansion candidates: {', '.join(final_candidates)}")

    # 5. Save and Export
    try:
        run_id = agent_results[0]["report_path"].split("/")[-3]
        metadata = {
            "seed_person": seed_person,
            "master_report": master_report,
            "expansion_candidates": final_candidates,
            "agents_involved": [r["agent_id"] for r in agent_results]
        }
        save_run_metadata(run_id, metadata)
        
        from margre.reporting.markdown import generate_final_report
        generate_final_report(run_id, master_report, metadata)
    except Exception as e:
        logger.error(f"AGGREGATOR: Failed to save final report: {e}")

    return {
        "master_report": master_report,
        "suggested_gaps": final_candidates, # Map candidates to suggested_gaps for the loop
        "messages": [HumanMessage(content=f"Discovery synthesized. {len(final_candidates)} candidates found for expansion.")],
    }
