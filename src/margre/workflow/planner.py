from langchain_core.messages import SystemMessage, HumanMessage
import logging
from margre.llm.client import get_model
from margre.workflow.state import OrchestratorState, DiscoveryPlan, DiscoveryTask
from margre.config import get_config
from margre.graph.repository import get_person_connections
from margre.llm.prompts import (
    DISCOVERY_PLANNER_SYSTEM_PROMPT,
    PLANNER_FALLBACK_SYSTEM_PROMPT,
    PLANNER_REFINEMENT_TEMPLATE,
    PLANNER_REVISION_TEMPLATE,
)

logger = logging.getLogger(__name__)

def planner_node(state: OrchestratorState) -> dict:
    """
    Decomposes the seed person into connection-oriented subtasks.
    """
    loop_count = state.get("loop_count", 0)
    seed_person = state['seed_person']
    logger.info(f"PLANNER: Analyzing connections for: {seed_person} (Loop: {loop_count})")
    
    model = get_model()
    
    # 1. Fetch existing knowledge from Neo4j
    connections = get_person_connections(seed_person)
    known_entities = [c['target_name'] for c in connections]
    logger.info(f"PLANNER: Found {len(connections)} existing connections for {seed_person} in graph.")

    # 2. Select the appropriate prompt
    revision_comments = state.get("plan_revision_comments")
    if revision_comments is not None:
        # HITL revision mode: user has commented on subtasks
        current_plan = state.get("plan")
        if current_plan and current_plan.subtasks:
            subtasks_lines = "\n".join(
                f"[{i+1}] {t.target_person} ({t.search_angle}): {t.research_query}"
                for i, t in enumerate(current_plan.subtasks)
            )
            system_content = PLANNER_REVISION_TEMPLATE.format(
                seed_person=seed_person,
                current_subtasks=subtasks_lines,
                user_feedback=revision_comments,
            )
            logger.info("PLANNER: Revising plan based on user feedback.")
        else:
            # No plan yet (first iteration) — fall through to normal planning
            system_content = DISCOVERY_PLANNER_SYSTEM_PROMPT.format(seed_person=seed_person)
    elif loop_count > 0 and state.get("suggested_gaps"):
        logger.info(f"PLANNER: Refining discovery based on {len(state['suggested_gaps'])} gaps.")
        system_content = PLANNER_REFINEMENT_TEMPLATE.format(
            topic=seed_person,
            master_summary=state.get("master_report", "No summary yet."),
            gaps=", ".join(state["suggested_gaps"])
        )
    else:
        system_content = DISCOVERY_PLANNER_SYSTEM_PROMPT.format(seed_person=seed_person)

    try:
        human_content = f"Discover connections for '{seed_person}'."
        if known_entities:
            human_content += f" We already know about: {', '.join(known_entities)}. Focus on finding NEW connections."

        prompt = [
            SystemMessage(content=system_content),
            HumanMessage(content=human_content)
        ]

        logger.debug(f"PLANNER: Sending prompt to LLM: {prompt}")

        structured_model = model.with_structured_output(schema=DiscoveryPlan)
        plan: DiscoveryPlan = structured_model.invoke(prompt)
        subtask_summaries = ", ".join([f"{t.target_person} ({t.search_angle})" for t in plan.subtasks])
        logger.info(f"PLANNER: Generated discovery plan with {len(plan.subtasks)} subtasks: {subtask_summaries}")

        revision_count = state.get("plan_revision_count", 0)
        if revision_comments:
            revision_count += 1
            logger.info(f"PLANNER: Revised plan with {len(plan.subtasks)} subtasks (revision #{revision_count})")

        return {
            "plan": plan,
            "messages": [HumanMessage(content=f"Discovery plan generated with {len(plan.subtasks)} tasks")],
            "user_approved_plan": False,
            "loop_count": loop_count + 1,
            "plan_revision_count": revision_count,
            "plan_revision_comments": None,
        }

    except Exception as e:
        logger.warning(f"PLANNER: Structured output failed (Error: {e}), falling back to manual JSON parsing...")
        
        fallback_prompt = [
            SystemMessage(content=PLANNER_FALLBACK_SYSTEM_PROMPT),
            HumanMessage(content=f"Identify discovery tasks for the social and professional network of: {seed_person}")
        ]
        
        logger.debug(f"PLANNER: Sending fallback prompt to LLM: {fallback_prompt}")
        raw_res = model.invoke(fallback_prompt).content
        
        import json
        try:
            if "```json" in raw_res:
                raw_res = raw_res.split("```json")[1].split("```")[0]
            elif "```" in raw_res:
                raw_res = raw_res.split("```")[1].split("```")[0]

            plan_dict = json.loads(raw_res.strip())
            # Basic validation/fix for fallback
            if "main_topic" in plan_dict and "seed_person" not in plan_dict:
                plan_dict["seed_person"] = plan_dict["main_topic"]

            # Normalize field name variants that LLMs commonly produce
            for task in plan_dict.get("subtasks", []):
                if "search_query" in task and "research_query" not in task:
                    task["research_query"] = task.pop("search_query")
                if "angle" in task and "search_angle" not in task:
                    task["search_angle"] = task.pop("angle")

            plan = DiscoveryPlan(**plan_dict)
            
            revision_count = state.get("plan_revision_count", 0)
            if revision_comments:
                revision_count += 1

            return {
                "plan": plan,
                "messages": [HumanMessage(content=f"Plan generated via fallback")],
                "user_approved_plan": False,
                "loop_count": loop_count + 1,
                "plan_revision_count": revision_count,
                "plan_revision_comments": None,
            }
        except Exception as json_err:
            logger.error(f"PLANNER: Fallback JSON parsing also failed: {json_err}. Raw response: {raw_res}")
            raise e


