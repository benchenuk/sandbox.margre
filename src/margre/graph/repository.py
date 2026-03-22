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
            result = session.run(query, url=url, title=title, snippet=snippet, file_path=file_path)
            return bool(list(result))
    except Exception as e:
        logger.error(f"Failed to save Source node: {e}")
        return False

def save_entity(label: str, properties: Dict[str, Any]) -> bool:
    """
    Save or update an entity (Person, Event, Organisation) in Neo4j.
    Uses MERGE on the 'name' property.
    """
    if label not in ["Person", "Event", "Organisation"]:
        logger.error(f"Unsupported entity label: {label}")
        return False
        
    # Build dynamic SET clause for properties
    set_clauses = []
    params = {"name": properties["name"]}
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
            result = session.run(query, **params)
            return bool(list(result))
    except Exception as e:
        logger.error(f"Failed to save {label} node: {e}")
        return False

def link_entity_to_source(entity_name: str, entity_label: str, source_url: str) -> bool:
    """Create a SOURCED_FROM relationship between an entity and a source."""
    query = f"""
    MATCH (e:{entity_label} {{name: $entity_name}})
    MATCH (s:Source {{url: $source_url}})
    MERGE (e)-[r:SOURCED_FROM]->(s)
    RETURN type(r)
    """
    driver = get_driver()
    try:
        with driver.session() as session:
            result = session.run(query, entity_name=entity_name, source_url=source_url)
            return bool(list(result))
    except Exception as e:
        logger.error(f"Failed to link entity to source: {e}")
        return False

def get_source_by_url(url: str) -> Dict[str, Any] | None:
    """Retrieve a Source node by its URL."""
    query = """
    MATCH (s:Source {url: $url})
    RETURN s
    """
    
    driver = get_driver()
    try:
        with driver.session() as session:
            result = session.run(query, url=url)
            records = list(result)
            if records:
                return dict(records[0]["s"])
            return None
    except Exception as e:
        logger.error(f"Failed to fetch Source node: {e}")
        return None
