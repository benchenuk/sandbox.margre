"""Neo4j graph database connection management."""

from neo4j import GraphDatabase, Driver
from margre.config import get_config

_driver: Driver | None = None

def get_driver() -> Driver:
    """Get the active Neo4j driver, initializing if necessary."""
    global _driver
    if _driver is None:
        config = get_config()
        _driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.username, config.neo4j.password)
        )
    return _driver

def close_driver():
    """Close the active driver connection."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None

def verify_connection() -> bool:
    """Verify the database connection."""
    try:
        driver = get_driver()
        driver.verify_connectivity()
        return True
    except Exception as e:
        import logging
        logging.error(f"Failed to connect to Neo4j: {e}")
        return False
