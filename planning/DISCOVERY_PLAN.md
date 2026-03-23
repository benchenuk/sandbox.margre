# MARGRe — Person-Centric Relationship Discovery Plan

> **Goal**: Shift MARGRe from topic-based research to **person-centric relationship discovery** — starting from a single individual, recursively discovering connections through direct acquaintance, shared works, shared locations and institutions, opposition/critique, and influence.

---

## What We Have vs What We Need

| Aspect | Current State | Target State |
|--------|--------------|--------------|
| **Entry Point** | Free-text topic query | A single person's name |
| **Planner Focus** | Decompose topic → subtasks | Discover *who* the person is connected to and *how* |
| **Researcher Focus** | General web search per subtask | Targeted search for relationships, shared contexts, works |
| **Graph Output** | Isolated entities (`Person`, `Event`, `Organisation`) with `SOURCED_FROM` links | Rich, temporally-annotated relationship edges (`KNEW`, `COLLABORATED_WITH`, `STUDIED_AT`, `CRITIQUED`, `INFLUENCED`, etc.) between `Person`, `Event`, `Institution`, `Work`, `Location` nodes |
| **Aggregator** | Synthesize a report | Deduplicate, merge into existing graph, suggest next persons to expand |
| **Iteration** | Refine same query | Pick the next discovered person and repeat (breadth expansion) |
| **Final Report** | Long narrative | High-level overview of all discovered individuals and their connections |

---

## Phased Implementation

### Phase A: Graph Schema Evolution

> **Goal**: Extend Neo4j schema to support rich, typed relationships between persons.

**Changes:**

#### [MODIFY] `graph/schema.py`

Add constraints and indexes for new relationship-aware schema:

- **Merge** `Organisation` into `Institution` (universities, companies, academies, guilds, courts — all under one label)
- **Keep** `Event` (battles, conferences, exhibitions, treaties, etc.)
- New node labels: `Institution`, `Work` (book, painting, theory, etc.), `Location`, `Event` (retained)
- All relationship properties include **temporal data**: `year` (integer, for timeline ordering) and optional `date` (string, for known specific dates like DoB or historic events). `period` is a human-readable string like "1490s" or "1508–1512".
- Relationship types are extensible — agents may propose new types in future versions.

```
# Person ↔ Person
(Person)-[:KNEW {context, period, year, date}]->(Person)
(Person)-[:COLLABORATED_WITH {work, period, year}]->(Person)
(Person)-[:INFLUENCED {domain, direction, period, year}]->(Person)
(Person)-[:CRITIQUED {work, context, year}]->(Person)
(Person)-[:OPPOSED {context, period, year}]->(Person)

# Person → Institution / Location / Work / Event
(Person)-[:STUDIED_AT {period, year}]->(Institution)
(Person)-[:WORKED_AT {role, period, year}]->(Institution)
(Person)-[:MEMBER_OF {role, period, year}]->(Institution)
(Person)-[:LIVED_IN {period, year}]->(Location)
(Person)-[:CREATED {year, date}]->(Work)
(Person)-[:CONTRIBUTED_TO {role, year}]->(Work)
(Person)-[:PARTICIPATED_IN {role, year, date}]->(Event)
```

#### [MODIFY] `graph/repository.py`

- Add `save_relationship(from_name, from_label, to_name, to_label, rel_type, properties)` — generic relationship writer using `MERGE`. Properties dict must support `year`, `date`, `period` alongside contextual fields.
- Add `get_person_connections(name)` — returns all relationships for a person (used by aggregator to check what we already know)
- Add `person_exists(name)` — check if we already have a person node (prevents redundant research)
- **Deprecate** `Organisation` label in favour of `Institution` (migration: relabel existing nodes)

---

### Phase B: Discovery-Oriented Planner

> **Goal**: Redesign the planner to focus on *discovering connections* for a given person, not decomposing a topic.

**Changes:**

#### [MODIFY] `workflow/state.py`

- Add `seed_person: str` to `OrchestratorState` — the person we are expanding from
- Add `discovered_persons: Annotated[List[str], operator.add]` — accumulates newly found names across loops
- Rename `SubTask` fields to reflect person-discovery:
  - `target_person` (the seed), `search_angle` (e.g., "collaborators", "opponents", "shared institutions"), `search_query`

#### [MODIFY] `llm/prompts.py`

New prompt: `DISCOVERY_PLANNER_PROMPT`

```
You are a biographical researcher. Given a person's name, 
generate 3-5 targeted search queries to discover:
1. Direct personal acquaintances and collaborators
2. People who influenced or were influenced by this person
3. Shared institutions (schools, employers, academies)
4. Critics or opponents
5. Co-authors or contributors to shared works

For each query, specify the search_angle (e.g., "collaborators", 
"institutional_peers", "critics") and a web search query string.
```

#### [MODIFY] `workflow/planner.py`

- Check Neo4j for existing connections of the seed person (`get_person_connections`)
- Pass existing knowledge to the LLM so it focuses on *gaps*, not things we already know
- Output: list of `DiscoveryTask` (search_angle + query)

---

### Phase C: Relationship-Aware Researcher

> **Goal**: Researcher agents extract *relationships* (not just entities) from search results.

**Changes:**

#### [MODIFY] `llm/prompts.py`

New prompt: `RELATIONSHIP_EXTRACTION_PROMPT`

```
From the following research text about {seed_person}, extract:
1. Other people mentioned and their relationship to {seed_person}
2. The type of relationship (knew, collaborated, influenced, critiqued, opposed, etc.)
3. Shared institutions, locations, events, or works
4. Temporal data for each relationship:
   - 'year' (integer) — the most relevant year for timeline ordering
   - 'date' (string, optional) — specific date if known (e.g. "1452-04-15" for DoB)
   - 'period' (string) — human-readable era or range (e.g. "1490s", "1508–1512")

Return structured data with: 
  discovered_persons[], relationships[], institutions[], works[], events[]
```

#### [MODIFY] `workflow/researcher.py`

- After synthesis, use `RELATIONSHIP_EXTRACTION_PROMPT` to extract structured relationship data
- New Pydantic schema: `DiscoveredRelationship(from_person, to_person, rel_type, context, year, date, period, source_url)`
- Call `save_relationship()` to persist edges to Neo4j
- Return `discovered_persons` list in agent results (for the aggregator to use)

#### [MODIFY] `workflow/state.py`

- New Pydantic model: `DiscoveryTask` replacing generic `SubTask`
- New extraction schema: `DiscoveredRelationship`

---

### Phase D: Graph-Aware Aggregator & Expansion Loop

> **Goal**: Aggregator deduplicates, merges into graph, and suggests *next persons* to expand.

**Changes:**

#### [MODIFY] `workflow/aggregator.py`

- Collect all `discovered_persons` from agent results
- Query Neo4j to filter out persons we have already deeply researched
- Rank remaining persons by frequency of mention (more mentions = higher priority)
- Return `expansion_candidates: List[str]` — the top N persons to research next
- Generate a brief overview report (not a deep narrative)

#### [MODIFY] `workflow/orchestrator.py`

- After aggregation, present `expansion_candidates` to the user via HITL
- User picks which persons to expand next (or all, or none)
- Loop back to Planner with the selected person as the new `seed_person`
- Track `depth` (how many hops from the original seed)

#### [MODIFY] `config.py`

- Add `max_expansion_depth: int` (default: 2) — how many hops from the seed
- Add `max_candidates_per_loop: int` (default: 3) — how many new persons to expand per iteration

---

### Phase E: CLI & Reporting Polish

> **Goal**: Update CLI commands and reporting to reflect the discovery workflow.

**Changes:**

#### [MODIFY] `cli.py`

- Rename/update `research` command to `discover`:
  ```
  margre discover "Leonardo da Vinci"
  ```
- Add `--depth` flag to control expansion depth
- Update `resume` to work with the new state
- Add `margre graph show <person>` — query Neo4j and display a person's connections in the terminal
- Update `margre runs list/show` to display discovery-specific metadata

#### [NEW] `reporting/overview.py`

- Generate a concise overview report listing all discovered persons and their relationships
- Format: table or brief bullet list per person, not a deep narrative
- Include a Mermaid diagram of the relationship graph (optional, for Markdown rendering)

---

## Execution Order

```
Phase A (Schema)     ← No workflow changes, safe to do first
    │
    ▼
Phase B (Planner)    ← New prompts + state changes
    │
    ▼
Phase C (Researcher) ← Relationship extraction
    │
    ▼
Phase D (Aggregator) ← Expansion loop
    │
    ▼
Phase E (CLI/Report) ← UX and presentation
```

Each phase is independently testable. Phase A can be verified with `margre init`. Phases B-D can be tested end-to-end with a single `margre discover "Name"` run.

---

## Verification Plan

### Automated
- After Phase A: Run `margre init` and verify new constraints are applied in Neo4j Browser
- After Phase C: Check that `runs/<id>/agents/*.json` contains `discovered_persons` and `relationships` arrays

### Manual (User)
- After Phase D: Run `margre discover "Leonardo da Vinci"` end-to-end
  - Verify the planner generates connection-oriented search queries
  - Verify Neo4j contains relationship edges (check in Neo4j Browser: `MATCH (p:Person)-[r]->(q:Person) RETURN p, r, q`)
  - Verify the expansion candidates are presented and selectable
- After Phase E: Run `margre graph show "Leonardo da Vinci"` and confirm terminal output lists connections
