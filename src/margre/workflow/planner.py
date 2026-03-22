"""Planning node logic."""

from langchain_core.messages import SystemMessage, HumanMessage
import logging
from margre.llm.client import get_model
from margre.workflow.state import OrchestratorState, ResearchPlan
from margre.config import get_config
from margre.llm.prompts import (
    PLANNER_SYSTEM_PROMPT,
    PLANNER_FALLBACK_SYSTEM_PROMPT
)

logger = logging.getLogger(__name__)

def planner_node(state: OrchestratorState) -> dict:
    """
    Decomposes the main query into a structured research plan with SubTasks.
    Uses the ChatOpenAI with `with_structured_output` to enforce schema.
    """
    logger.info(f"PLANNER: Analyzing query: {state['query']}")
    config = get_config()
    model = get_model()
    
    try:
        structured_model = model.with_structured_output(schema=ResearchPlan)
        
        prompt = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT.format(max_agents=config.workflow.max_agents_per_run)),
            HumanMessage(content=f"Decompose this research query: '{state['query']}'")
        ]
        
        logger.debug(f"PLANNER: Sending prompt to LLM: {prompt}")
        plan: ResearchPlan = structured_model.invoke(prompt)
        
        subtask_summaries = ", ".join([f"{t.entity_name} ({t.entity_type})" for t in plan.subtasks])
        logger.info(f"PLANNER: Generated plan with {len(plan.subtasks)} subtasks: {subtask_summaries}")
        
        return {
            "plan": plan,
            "messages": [HumanMessage(content=f"Plan generated with {len(plan.subtasks)} tasks")],
            "user_approved_plan": False
        }
        
    except Exception as e:
        logger.warning(f"PLANNER: Structured output failed (Error: {e}), falling back to manual JSON parsing...")
        
        fallback_prompt = [
            SystemMessage(content=PLANNER_FALLBACK_SYSTEM_PROMPT),
            HumanMessage(content=f"Decompose this query: {state['query']}")
        ]
        
        logger.debug(f"PLANNER: Sending fallback prompt to LLM: {fallback_prompt}")
        raw_res = model.invoke(fallback_prompt).content
        logger.debug(f"PLANNER: Received raw response: {raw_res}")
        
        import json
        try:
            if "```json" in raw_res:
                raw_res = raw_res.split("```json")[1].split("```")[0]
            elif "```" in raw_res:
                raw_res = raw_res.split("```")[1].split("```")[0]
            
            plan_dict = json.loads(raw_res.strip())
            plan = ResearchPlan(**plan_dict)
            
            subtask_summaries = ", ".join([f"{t.entity_name} ({t.entity_type})" for t in plan.subtasks])
            logger.info(f"PLANNER: Generated plan via fallback with {len(plan.subtasks)} subtasks: {subtask_summaries}")
            
            return {
                "plan": plan,
                "messages": [HumanMessage(content=f"Plan generated via fallback")],
                "user_approved_plan": False
            }
        except Exception as json_err:
            logger.error(f"PLANNER: Fallback JSON parsing also failed: {json_err}. Raw response: {raw_res}")
            raise e
