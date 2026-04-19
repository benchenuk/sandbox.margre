"""Synthesis node for creating the master discovery report."""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from margre.llm.client import get_model
from margre.workflow.state import OrchestratorState
from margre.llm.prompts import AGGREGATOR_SYSTEM_PROMPT
from margre.persistence.runs import save_run_metadata

logger = logging.getLogger(__name__)


def synthesis_node(state: OrchestratorState) -> dict:
    """
    Synthesizes all sub-agent reports into a single master discovery report.
    """
    seed_person = state["seed_person"]
    agent_results = state.get("agent_results", [])
    logger.info(f"SYNTHESIS: Synthesizing results for: {seed_person}")

    if not agent_results:
        return {
            "master_report": "No discovery results to aggregate.",
            "messages": [SystemMessage(content="No discovery results to aggregate.")],
        }

    model = get_model()

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
            logger.warning(f"SYNTHESIS: Could not read report for {agent_id}: {e}")

    full_context = "\n\n".join(context_chunks)

    synthesis_prompt = [
        SystemMessage(content=AGGREGATOR_SYSTEM_PROMPT.format(topic=seed_person)),
        HumanMessage(
            content=f"Sub-Agent Discovery Reports:\n\n{full_context}\n\nPlease synthesize a final overview of {seed_person}'s connections."
        ),
    ]
    master_report = model.invoke(synthesis_prompt).content

    return {
        "master_report": master_report,
    }
