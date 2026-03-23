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
    Save or update an entity (Person, Event, Institution, Work, Location) in Neo4j.
    Uses MERGE on the 'name' property.
    """
    allowed_labels = ["Person", "Event", "Institution", "Work", "Location"]
    if label not in allowed_labels:
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
        
    set_str = (", ".join(set_clauses) + ", ") if set_clauses else ""
    query = f"""
    MERGE (n:{label} {{name: $name}})
    ON CREATE SET {set_str}n.created_at = datetime()
    ON MATCH SET {set_str}n.updated_at = datetime()
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

def save_relationship(from_name: str, from_label: str, to_name: str, to_label: str, rel_type: str, properties: Dict[str, Any]) -> bool:
    """
    Create a typed relationship between two entities.
    Example: save_relationship("Leonardo", "Person", "Verrocchio", "Person", "STUDIED_WITH", {"year": 1466})
    """
    logger.info(f"GRAPH: Saving relationship: ({from_name})-[{rel_type}]->({to_name})")
    
    # Build dynamic SET clause for relationship properties
    set_clauses = []
    params = {
        "from_name": from_name,
        "to_name": to_name
    }
    for key, value in properties.items():
        set_clauses.append(f"r.{key} = ${key}")
        params[key] = value
    
    set_str = "SET " + ", ".join(set_clauses) if set_clauses else ""
    
    query = f"""
    MATCH (a:{from_label} {{name: $from_name}})
    MATCH (b:{to_label} {{name: $to_name}})
    MERGE (a)-[r:{rel_type}]->(b)
    {set_str}
    RETURN type(r)
    """
    
    driver = get_driver()
    try:
        with driver.session() as session:
            result = session.run(query, **params)
            success = bool(list(result))
            return success
    except Exception as e:
        logger.error(f"GRAPH: Failed to save relationship: {e}")
        return False

def person_exists(name: str) -> bool:
    """Check if a person node already exists in the graph."""
    query = "MATCH (p:Person {name: $name}) RETURN p.name as name"
    driver = get_driver()
    try:
        with driver.session() as session:
            result = session.run(query, name=name)
            return bool(list(result))
    except Exception:
        return False

def get_person_connections(name: str) -> List[Dict[str, Any]]:
    """Retrieve all direct relationships for a person."""
    query = """
    MATCH (p:Person {name: $name})-[r]->(target)
    RETURN type(r) as rel_type, labels(target)[0] as target_label, target.name as target_name, properties(r) as props
    """
    driver = get_driver()
    connections = []
    try:
        with driver.session() as session:
            result = session.run(query, name=name)
            for record in result:
                connections.append({
                    "rel_type": record["rel_type"],
                    "target_label": record["target_label"],
                    "target_name": record["target_name"],
                    "properties": record["props"]
                })
    except Exception as e:
        logger.error(f"GRAPH: Failed to get person connections: {e}")
    return connections

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
            result = session.run(query, entity_name=entity_name, source_url=source_url)
            return bool(list(result))
    except Exception as e:
        logger.error(f"GRAPH: Failed to link entity to source: {e}")
        return False

def get_source_by_url(url: str) -> Dict[str, Any] | None:
    """Retrieve a Source node by its URL."""
    query = "MATCH (s:Source {url: $url}) RETURN s"
    driver = get_driver()
    try:
        with driver.session() as session:
            result = session.run(query, url=url)
            records = list(result)
            return dict(records[0]["s"]) if records else None
    except Exception:
        return None
