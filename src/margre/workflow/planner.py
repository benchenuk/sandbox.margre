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
    logger.info(f"Running planner for query: {state['query']}")
    config = get_config()
    model = get_model()
    
    # Check if the model supports native tool calling/structured output
    # If using local generic models, we might need a standard prompt instead
    # Langchain's with_structured_output typically uses tool calling. Let's try it first.
    try:
        structured_model = model.with_structured_output(schema=ResearchPlan)
        
        prompt = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT.format(max_agents=config.workflow.max_agents_per_run)),
            HumanMessage(content=f"Decompose this research query: '{state['query']}'")
        ]
        
        plan: ResearchPlan = structured_model.invoke(prompt)
        logger.info(f"Generated plan with {len(plan.subtasks)} subtasks")
        
        # Save to state
        return {
            "plan": plan,
            "messages": [HumanMessage(content=f"Plan generated with {len(plan.subtasks)} tasks")],
            "user_approved_plan": False  # Hand off to HITL loop
        }
        
    except Exception as e:
        logger.warning(f"Structured output failed ({e}), falling back to manual JSON parsing...")
        
        # Fallback for models without tool-call support
        fallback_prompt = [
            SystemMessage(content=PLANNER_FALLBACK_SYSTEM_PROMPT),
            HumanMessage(content=f"Decompose this query: {state['query']}")
        ]
        
        raw_res = model.invoke(fallback_prompt).content
        import json
        try:
            # Simple cleanup to find JSON block
            if "```json" in raw_res:
                raw_res = raw_res.split("```json")[1].split("```")[0]
            elif "```" in raw_res:
                raw_res = raw_res.split("```")[1].split("```")[0]
            
            plan_dict = json.loads(raw_res.strip())
            plan = ResearchPlan(**plan_dict)
            return {
                "plan": plan,
                "messages": [HumanMessage(content=f"Plan generated via fallback")],
                "user_approved_plan": False
            }
        except Exception as json_err:
            logger.error(f"Fallback JSON parsing also failed: {json_err}")
            raise e
