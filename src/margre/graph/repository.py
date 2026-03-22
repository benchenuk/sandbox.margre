"""Graph repository for operations handling persistence to Neo4j."""

from typing import Dict, Any, List
import logging
from margre.graph.connection import get_driver

logger = logging.getLogger(__name__)

def save_source(url: str, title: str, snippet: str, file_path: str = "") -> bool:
    """
    Save or update a Source node in Neo4j.
    Returns True if successful, False otherwise.
    """
    logger.info(f"GRAPH: Saving Source node: {url}")
    query = """
    MERGE (s:Source {url: $url})
    ON CREATE SET s.title = $title,
                  s.snippet = $snippet,
                  s.file_path = $file_path,
                  s.retrieved_at = datetime()
    ON MATCH SET s.title = COALESCE($title, s.title),
                 s.snippet = COALESCE($snippet, s.snippet),
                 s.file_path = CASE WHEN $file_path <> "" THEN $file_path ELSE s.file_path END,
                 s.retrieved_at = datetime()
    RETURN s.url as url
    """
    
    driver = get_driver()
    try:
        with driver.session() as session:
            logger.debug(f"GRAPH: Executing Cypher:\n{query}\nParams: url={url}, title={title}")
            result = session.run(query, url=url, title=title, snippet=snippet, file_path=file_path)
            success = bool(list(result))
            if success:
                logger.info(f"GRAPH: Successfully saved Source node: {url}")
            return success
    except Exception as e:
        logger.error(f"GRAPH: Failed to save Source node: {e}")
        return False

def save_entity(label: str, properties: Dict[str, Any]) -> bool:
    """
    Save or update an entity (Person, Event, Organisation) in Neo4j.
    Uses MERGE on the 'name' property.
    """
    if label not in ["Person", "Event", "Organisation"]:
        logger.error(f"GRAPH: Unsupported entity label: {label}")
        return False
        
    name = properties.get("name")
    if not name:
        logger.error(f"GRAPH: Entity properties missing 'name': {properties}")
        return False
        
    logger.info(f"GRAPH: Saving {label} node: {name}")
    
    # Build dynamic SET clause for properties
    set_clauses = []
    params = {"name": name}
    for key, value in properties.items():
        if key == "name":
            continue
        set_clauses.append(f"n.{key} = ${key}")
        params[key] = value
        
    set_str = ", ".join(set_clauses)
    query = f"""
    MERGE (n:{label} {{name: $name}})
    ON CREATE SET {set_str}, n.created_at = datetime()
    ON MATCH SET {set_str}, n.updated_at = datetime()
    RETURN n.name as name
    """
    
    driver = get_driver()
    try:
        with driver.session() as session:
            logger.debug(f"GRAPH: Executing Cypher:\n{query}\nParams: {params}")
            result = session.run(query, **params)
            success = bool(list(result))
            if success:
                logger.info(f"GRAPH: Successfully saved {label} node: {name}")
            return success
    except Exception as e:
        logger.error(f"GRAPH: Failed to save {label} node: {e}")
        return False

def link_entity_to_source(entity_name: str, entity_label: str, source_url: str) -> bool:
    """Create a SOURCED_FROM relationship between an entity and a source."""
    logger.info(f"GRAPH: Linking {entity_label} '{entity_name}' to Source: {source_url}")
    query = f"""
    MATCH (e:{entity_label} {{name: $entity_name}})
    MATCH (s:Source {{url: $source_url}})
    MERGE (e)-[r:SOURCED_FROM]->(s)
    RETURN type(r)
    """
    driver = get_driver()
    try:
        with driver.session() as session:
            logger.debug(f"GRAPH: Executing Cypher:\n{query}\nParams: entity_name={entity_name}, source_url={source_url}")
            result = session.run(query, entity_name=entity_name, source_url=source_url)
            success = bool(list(result))
            if success:
                logger.info(f"GRAPH: Successfully linked {entity_name} to {source_url}")
            return success
    except Exception as e:
        logger.error(f"GRAPH: Failed to link entity to source: {e}")
        return False

def get_source_by_url(url: str) -> Dict[str, Any] | None:
    """Retrieve a Source node by its URL."""
    logger.info(f"GRAPH: Fetching Source node by URL: {url}")
    query = """
    MATCH (s:Source {url: $url})
    RETURN s
    """
    
    driver = get_driver()
    try:
        with driver.session() as session:
            logger.debug(f"GRAPH: Executing Cypher:\n{query}\nParams: url={url}")
            result = session.run(query, url=url)
            records = list(result)
            if records:
                logger.info(f"GRAPH: Source node found for URL: {url}")
                return dict(records[0]["s"])
            logger.info(f"GRAPH: No Source node found for URL: {url}")
            return None
    except Exception as e:
        logger.error(f"GRAPH: Failed to fetch Source node: {e}")
        return None
