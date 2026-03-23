from langchain_core.messages import SystemMessage, HumanMessage
import logging
from margre.llm.client import get_model
from margre.workflow.state import OrchestratorState, DiscoveryPlan
from margre.config import get_config
from margre.graph.repository import get_person_connections
from margre.llm.prompts import (
    DISCOVERY_PLANNER_SYSTEM_PROMPT, 
    PLANNER_FALLBACK_SYSTEM_PROMPT,
    PLANNER_REFINEMENT_TEMPLATE
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
    if loop_count > 0 and state.get("suggested_gaps"):
        logger.info(f"PLANNER: Refining discovery based on {len(state['suggested_gaps'])} gaps.")
        system_content = PLANNER_REFINEMENT_TEMPLATE.format(
            topic=seed_person,
            master_summary=state.get("master_report", "No summary yet."),
            gaps=", ".join(state["suggested_gaps"])
        )
    else:
        system_content = DISCOVERY_PLANNER_SYSTEM_PROMPT.format(seed_person=seed_person)

    try:
        structured_model = model.with_structured_output(schema=DiscoveryPlan)
        
        human_content = f"Discover connections for '{seed_person}'."
        if known_entities:
            human_content += f" We already know about: {', '.join(known_entities)}. Focus on finding NEW connections."
            
        prompt = [
            SystemMessage(content=system_content),
            HumanMessage(content=human_content)
        ]
        
        logger.debug(f"PLANNER: Sending prompt to LLM: {prompt}")
        plan: DiscoveryPlan = structured_model.invoke(prompt)
        
        subtask_summaries = ", ".join([f"{t.target_person} ({t.search_angle})" for t in plan.subtasks])
        logger.info(f"PLANNER: Generated discovery plan with {len(plan.subtasks)} subtasks: {subtask_summaries}")
        
        return {
            "plan": plan,
            "messages": [HumanMessage(content=f"Discovery plan generated with {len(plan.subtasks)} tasks")],
            "user_approved_plan": False,
            "loop_count": loop_count + 1
        }
        
    except Exception as e:
        logger.warning(f"PLANNER: Structured output failed (Error: {e}), falling back to manual JSON parsing...")
        
        fallback_prompt = [
            SystemMessage(content=PLANNER_FALLBACK_SYSTEM_PROMPT),
            HumanMessage(content=f"Decompose this query and focus on gaps if provided: {seed_person}")
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
                
            plan = DiscoveryPlan(**plan_dict)
            
            return {
                "plan": plan,
                "messages": [HumanMessage(content=f"Plan generated via fallback")],
                "user_approved_plan": False,
                "loop_count": loop_count + 1
            }
        except Exception as json_err:
            logger.error(f"PLANNER: Fallback JSON parsing also failed: {json_err}. Raw response: {raw_res}")
            raise e
