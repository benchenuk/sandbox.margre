"""Neo4j schema constraints setup."""

from typing import List
from margre.graph.connection import get_driver

def init_schema() -> List[str]:
    """
    Initialize Neo4j schema definitions.
    Requires at least admin permissions or schema creation access.
    """
    queries = [
        "CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT event_name IF NOT EXISTS FOR (e:Event) REQUIRE e.name IS UNIQUE",
        "CREATE CONSTRAINT org_name IF NOT EXISTS FOR (o:Organisation) REQUIRE o.name IS UNIQUE",
        "CREATE CONSTRAINT source_url IF NOT EXISTS FOR (s:Source) REQUIRE s.url IS UNIQUE",
        "CREATE CONSTRAINT run_id IF NOT EXISTS FOR (r:ResearchRun) REQUIRE r.run_id IS UNIQUE",
    ]
    
    results = []
    driver = get_driver()
    with driver.session() as session:
        for q in queries:
            try:
                session.run(q)
                results.append(f"Successfully applied constraint: {q.split('FOR')[0].strip()}")
            except Exception as e:
                results.append(f"Error applying {q}: {e}")
                
    return results
