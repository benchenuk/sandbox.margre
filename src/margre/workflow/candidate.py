"""Candidate node for identifying and ranking expansion candidates."""

import logging
from collections import Counter
from langchain_core.messages import HumanMessage
from margre.workflow.state import OrchestratorState, Candidate
from margre.config import get_config
from margre.graph.repository import person_exists
from margre.persistence.runs import save_run_metadata

logger = logging.getLogger(__name__)


def candidate_node(state: OrchestratorState) -> dict:
    """
    Identifies expansion candidates from discovered persons.
    Deduplicates, ranks by frequency, filters against Neo4j,
    and caps at max_candidates_per_loop.
    """
    seed_person = state["seed_person"]
    agent_results = state.get("agent_results", [])
    logger.info(f"CANDIDATE: Identifying expansion candidates for: {seed_person}")

    all_discovered = state.get("discovered_persons", [])
    candidates = [p for p in all_discovered if p.lower() != seed_person.lower()]

    counts = Counter(candidates)

    unique_candidates = []
    for name, count in counts.most_common():
        if not person_exists(name):
            unique_candidates.append(Candidate(name=name, score=float(count)))
        else:
            logger.debug(f"CANDIDATE: Skipping {name} (already in graph).")

    config = get_config()
    limit = config.workflow.max_candidates_per_loop
    final_candidates = unique_candidates[:limit]
    dropped = unique_candidates[limit:]

    if dropped:
        logger.info(
            f"CANDIDATE: Dropped {len(dropped)} candidates due to limit ({limit}): {', '.join(c.name for c in dropped)}"
        )

    logger.info(
        f"CANDIDATE: Identified {len(final_candidates)} expansion candidates: {', '.join(c.name for c in final_candidates)}"
    )

    try:
        run_id = agent_results[0]["report_path"].split("/")[-3]
        metadata = {
            "seed_person": seed_person,
            "master_report": state.get("master_report"),
            "expansion_candidates": [c.name for c in final_candidates],
            "agents_involved": [r["agent_id"] for r in agent_results],
        }
        save_run_metadata(run_id, metadata)

        from margre.reporting.markdown import generate_final_report

        generate_final_report(run_id, state.get("master_report", ""), metadata)
    except Exception as e:
        logger.error(f"CANDIDATE: Failed to save final report: {e}")

    return {
        "suggested_gaps": final_candidates,
        "messages": [
            HumanMessage(
                content=f"Discovery synthesized. {len(final_candidates)} candidates found for expansion."
            )
        ],
    }
