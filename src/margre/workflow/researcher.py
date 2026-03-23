import logging
from langchain_core.messages import SystemMessage, HumanMessage
from margre.workflow.state import ResearcherState, DiscoveryExtractionResult
from margre.llm.client import get_model
from margre.search import get_search_provider
from margre.persistence.notes import save_research_note
from margre.persistence.runs import save_agent_structured_result
from margre.graph.repository import save_entity, save_source, link_entity_to_source, save_relationship
from margre.llm.prompts import (
    RESEARCHER_SYNTHESIS_SYSTEM_PROMPT,
    RESEARCHER_SYNTHESIS_HUMAN_TEMPLATE,
    RELATIONSHIP_EXTRACTION_PROMPT
)

logger = logging.getLogger(__name__)

def researcher_node(state: ResearcherState) -> dict:
    """
    Executes a single discovery subtask.
    1. Web Search
    2. Synthesis (Markdown)
    3. Relationship Extraction
    4. Persistence (Neo4j + Filesystem)
    """
    subtask = state["subtask"]
    agent_id = state["agent_id"]
    run_id = state["run_id"]
    seed_person = subtask.target_person
    
    logger.info(f"RESEARCHER [{agent_id}]: Discovering connections for: {seed_person} ({subtask.search_angle})")
    
    # 1. Search
    provider = get_search_provider()
    search_results = provider.search(subtask.research_query, max_results=5)
    
    if not search_results:
        logger.warning(f"RESEARCHER [{agent_id}]: No results for: '{subtask.research_query}'")
        return {
            "final_report": f"No new connections found for {seed_person} in this angle.",
            "structured_data": {}
        }

    # 2. Synthesis (Narrative Report)
    model = get_model()
    sources_text = "\n\n".join([f"Source: {r.url}\nTitle: {r.title}\nSnippet: {r.snippet}" for r in search_results])
    
    synthesis_prompt = [
        SystemMessage(content=RESEARCHER_SYNTHESIS_SYSTEM_PROMPT),
        HumanMessage(content=RESEARCHER_SYNTHESIS_HUMAN_TEMPLATE.format(
            query=subtask.research_query,
            entity_name=seed_person,
            entity_type="Person",
            snippets=sources_text
        ))
    ]
    report = model.invoke(synthesis_prompt).content
    report_path = save_research_note(run_id, agent_id, report)

    # 3. Extraction (Relationships)
    extraction_prompt = [
        SystemMessage(content=RELATIONSHIP_EXTRACTION_PROMPT.format(seed_person=seed_person)),
        HumanMessage(content=f"Research Report about {seed_person}:\n{report}")
    ]
    
    logger.info(f"RESEARCHER [{agent_id}]: Extracting relationships.")
    structured_model = model.with_structured_output(schema=DiscoveryExtractionResult)
    
    try:
        extracted: DiscoveryExtractionResult = structured_model.invoke(extraction_prompt)
    except Exception as e:
        logger.warning(f"RESEARCHER [{agent_id}]: Structured extraction failed ({e}). Falling back to manual JSON parsing...")
        raw_res = model.invoke(extraction_prompt).content
        
        import json
        try:
            if "```json" in raw_res:
                raw_res = raw_res.split("```json")[1].split("```")[0]
            elif "```" in raw_res:
                raw_res = raw_res.split("```")[1].split("```")[0]
            
            data = json.loads(raw_res.strip())
            extracted = DiscoveryExtractionResult(**data)
        except Exception as json_err:
            logger.error(f"RESEARCHER [{agent_id}]: Manual parsing failed: {json_err}. Returning empty result.")
            extracted = DiscoveryExtractionResult(relationships=[], new_persons=[])
    
    # 4. Persistence
    # Save search sources
    for r in search_results:
        save_source(r.url, r.title, r.snippet, file_path=report_path)

    # Ensure seed person exists
    save_entity("Person", {"name": seed_person})

    rel_count = 0
    for rel in extracted.relationships:
        # Create/Update target entity
        target_props = {"name": rel.target_name}
        if save_entity(rel.target_label, target_props):
            # Create typed relationship with temporal data
            rel_props = {
                "context": rel.context,
                "year": rel.year,
                "date": rel.date,
                "period": rel.period,
                "agent_id": agent_id
            }
            # Clean None values for Neo4j
            rel_props = {k: v for k, v in rel_props.items() if v is not None}
            
            if save_relationship(seed_person, "Person", rel.target_name, rel.target_label, rel.rel_type, rel_props):
                rel_count += 1
                if search_results:
                    link_entity_to_source(rel.target_name, rel.target_label, search_results[0].url)

    logger.info(f"RESEARCHER [{agent_id}]: Persisted {rel_count} new relationships to Neo4j.")
    
    # Save structured summary for debugging
    save_agent_structured_result(run_id, agent_id, extracted.model_dump())

    return {
        "discovered_persons": extracted.new_persons,
        "agent_results": [{
            "agent_id": agent_id,
            "seed_person": seed_person,
            "report_path": report_path,
            "rel_count": rel_count
        }]
    }
