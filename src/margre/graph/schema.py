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
        "CREATE CONSTRAINT inst_name IF NOT EXISTS FOR (i:Institution) REQUIRE i.name IS UNIQUE",
        "CREATE CONSTRAINT work_name IF NOT EXISTS FOR (w:Work) REQUIRE w.name IS UNIQUE",
        "CREATE CONSTRAINT loc_name IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE",
        "CREATE CONSTRAINT source_url IF NOT EXISTS FOR (s:Source) REQUIRE s.url IS UNIQUE",
        "CREATE CONSTRAINT run_id IF NOT EXISTS FOR (r:ResearchRun) REQUIRE r.run_id IS UNIQUE",
        # Migration: Relabel Organisation to Institution 
        "MATCH (o:Organisation) REMOVE o:Organisation SET o:Institution"
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
