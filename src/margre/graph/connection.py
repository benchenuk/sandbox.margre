"""Neo4j graph database connection management."""

import logging

from neo4j import GraphDatabase, Driver
from margre.config import get_config

logger = logging.getLogger(__name__)

_driver: Driver | None = None

def get_driver() -> Driver:
    """Get the active Neo4j driver, initializing if necessary.

    Configures connection pooling and lifetime settings for resilience
    against stale connections and long-running sessions.
    """
    global _driver
    if _driver is None:
        config = get_config()
        logger.info(f"NEO4J: Opening new driver connection to {config.neo4j.uri}")
        _driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.username, config.neo4j.password),
            max_connection_lifetime=3600,         # Reconnect every hour to avoid stale connections
            max_connection_pool_size=50,          # Allow up to 50 concurrent sessions
            connection_acquisition_timeout=30,     # Seconds to wait for a pool connection
            connection_timeout=15,                # Seconds to wait for a TCP connection
        )
    return _driver

def close_driver():
    """Close the active driver connection."""
    global _driver
    if _driver is not None:
        _driver.close()
        logger.info("NEO4J: Driver connection closed.")
    _driver = None

def verify_connection() -> bool:
    """Verify the database connection. Fails fast — no retries."""
    try:
        driver = get_driver()
        driver.verify_connectivity()
        return True
    except Exception as e:
        logger.error(f"NEO4J: Connection failed: {e}")
        return False
