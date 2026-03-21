# MARGRe — Implementation Plan

> **Status**: Draft — pending review  
> **Last Updated**: 2026-03-19  
> **Reference**: [REQUIREMENTS.md](./REQUIREMENTS.md)

---

## Architectural Decisions

### AD-1: Dual Persistence Strategy
- **Neo4j** stores structured data: entities (Person, Event, Organisation, Source), relationships, and workflow metadata.
- **Filesystem** stores narrative content: Markdown research notes and JSON metadata per run.
- Neo4j `Source` nodes hold a `file_path` property linking to the filesystem artifact.

### AD-2: LangGraph Orchestrator-Worker Pattern
- A top-level LangGraph `StateGraph` manages the 4-phase workflow (Plan → Research → Aggregate → Loop/Exit).
- The orchestrator uses LangGraph's `Send` API to dynamically spawn parallel research sub-agents.
- Each sub-agent is a self-contained subgraph with its own tools (search, note-writing).

### AD-3: OpenAI-Compatible LLM Client
- All LLM calls go through a single client using the OpenAI Python SDK pointed at a configurable `base_url`.
- No coupling to any specific provider — works with any OpenAI-like endpoint.

### AD-4: Pluggable Search Interface
- Abstract `SearchProvider` protocol with `search(query) -> list[SearchResult]`.
- Two implementations: `DDGSSearchProvider` and `SearXNGSearchProvider`.
- Active provider selected via `config.toml`.

---

## Project Structure

```
margre/
├── pyproject.toml              # uv/pip project metadata
├── config.toml.example         # Example configuration
├── README.md
├── planning/                   # Design docs (this file, requirements, etc.)
│
├── src/
│   └── margre/
│       ├── __init__.py
│       ├── cli.py              # CLI entry point (typer + rich)
│       ├── config.py           # TOML config loading
│       │
│       ├── llm/
│       │   ├── __init__.py
│       │   └── client.py       # OpenAI-compatible LLM client
│       │
│       ├── search/
│       │   ├── __init__.py
│       │   ├── base.py         # SearchProvider protocol
│       │   ├── ddgs.py         # DuckDuckGo implementation
│       │   └── searxng.py      # SearXNG implementation
│       │
│       ├── graph/
│       │   ├── __init__.py
│       │   ├── connection.py   # Neo4j driver/session management
│       │   ├── schema.py       # Node/relationship type definitions
│       │   └── repository.py   # CRUD operations (Cypher queries)
│       │
│       ├── workflow/
│       │   ├── __init__.py
│       │   ├── state.py        # LangGraph state definitions
│       │   ├── orchestrator.py # Top-level graph (Plan→Research→Aggregate→Loop)
│       │   ├── planner.py      # Planning node
│       │   ├── researcher.py   # Research sub-agent subgraph
│       │   ├── aggregator.py   # Aggregation node
│       │   └── hitl.py         # Human-in-the-loop interrupt handling
│       │
│       ├── persistence/
│       │   ├── __init__.py
│       │   ├── notes.py        # Markdown note read/write
│       │   └── runs.py         # Run metadata (JSON) management
│       │
│       └── reporting/
│           ├── __init__.py
│           └── markdown.py     # Final report generation
│
├── runs/                       # Runtime output (gitignored)
│   └── <run-id>/
│       ├── plan.json           # Research plan
│       ├── agents/
│       │   ├── <agent-id>.md   # Per-agent research notes
│       │   └── <agent-id>.json # Per-agent structured results
│       ├── aggregation.json    # Aggregated results
│       └── report.md           # Final report
│
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_search/
    ├── test_graph/
    └── test_workflow/
```

---

## Phased Implementation

Each phase produces a **demonstrable, working increment** that can be tested independently.

---

### Phase 1: Foundation & Infrastructure

> **Goal**: Project skeleton, configuration, LLM client, and Neo4j connectivity.  
> **Deliverable**: CLI that loads config, connects to Neo4j, and makes a test LLM call.

| Step | Description | Files | Requirements |
|------|-------------|-------|--------------|
| 1.1 | Project scaffolding with `uv`, `pyproject.toml`, directory structure | `pyproject.toml`, `src/margre/__init__.py` | — |
| 1.2 | TOML config loading | `config.py`, `config.toml.example` | NFR-2 |
| 1.3 | OpenAI-compatible LLM client | `llm/client.py` | NFR-3 |
| 1.4 | Neo4j connection manager | `graph/connection.py` | FR-4 |
| 1.5 | Neo4j schema bootstrap (constraints, indexes) | `graph/schema.py` | FR-4 |
| 1.6 | CLI entry point with `typer` + `rich` | `cli.py` | NFR-1 |
| 1.7 | Docker Compose for local Neo4j | `docker-compose.yml` | FR-4 |
| 1.8 | Basic tests and CI validation | `tests/` | — |

**Demo**: `margre init` — initialises config, connects to Neo4j, runs a health check LLM call, prints results with color.

---

### Phase 2: Search & Persistence Layer

> **Goal**: Pluggable search and filesystem persistence for research notes.  
> **Deliverable**: CLI command that searches the web and saves results as Markdown + JSON.

| Step | Description | Files | Requirements |
|------|-------------|-------|--------------|
| 2.1 | `SearchProvider` protocol | `search/base.py` | FR-5, NFR-5 |
| 2.2 | DDGS implementation | `search/ddgs.py` | FR-5 |
| 2.3 | SearXNG implementation | `search/searxng.py` | FR-5 |
| 2.4 | Search provider factory (config-driven) | `search/__init__.py` | FR-5, NFR-2 |
| 2.5 | Filesystem note persistence (Markdown) | `persistence/notes.py` | FR-7 |
| 2.6 | Run metadata persistence (JSON) | `persistence/runs.py` | FR-7 |
| 2.7 | Neo4j `Source` node repository | `graph/repository.py` | FR-4, FR-5 |
| 2.8 | Tests for search + persistence | `tests/` | — |

**Demo**: `margre search "Machiavelli allies"` — searches via configured provider, saves results to `./runs/<id>/`, writes `Source` nodes to Neo4j.

---

### Phase 3: Core Workflow — Planning & Research

> **Goal**: LangGraph workflow with the Plan and Research phases.  
> **Deliverable**: End-to-end query → plan → parallel research, with HITL at planning.

| Step | Description | Files | Requirements |
|------|-------------|-------|--------------|
| 3.1 | LangGraph state schema | `workflow/state.py` | FR-1 |
| 3.2 | Planner node (LLM decomposes query into subtasks) | `workflow/planner.py` | FR-1, FR-2 |
| 3.3 | HITL interrupt after planning | `workflow/hitl.py` | FR-3 |
| 3.4 | Researcher sub-agent subgraph (search + note-writing) | `workflow/researcher.py` | FR-2, FR-5 |
| 3.5 | Dynamic dispatch via `Send` API | `workflow/orchestrator.py` | FR-2 |
| 3.6 | Neo4j entity writing (Person, Event, Organisation) | `graph/repository.py` | FR-4 |
| 3.7 | Wire CLI `research` command to the workflow | `cli.py` | NFR-1 |
| 3.8 | Integration tests for the workflow graph | `tests/test_workflow/` | — |

**Demo**: `margre research "Renaissance political alliances"` — shows plan, pauses for approval, spawns parallel research agents, writes notes to disk + entities to Neo4j.

---

### Phase 4: Aggregation, Reporting & Loop

> **Goal**: Complete the workflow loop with aggregation, HITL review, and report generation.  
> **Deliverable**: Full loop — query → plan → research → aggregate → review → loop/exit → report.

| Step | Description | Files | Requirements |
|------|-------------|-------|--------------|
| 4.1 | Aggregator node (cross-reference, dedup, gap detection) | `workflow/aggregator.py` | FR-6 |
| 4.2 | HITL interrupt after aggregation | `workflow/hitl.py` | FR-3 |
| 4.3 | Loop-or-exit decision logic | `workflow/orchestrator.py` | FR-1 |
| 4.4 | Markdown report generation | `reporting/markdown.py` | FR-6 |
| 4.5 | Wire loop + report to CLI | `cli.py` | NFR-1 |
| 4.6 | End-to-end integration tests | `tests/test_workflow/` | — |

**Demo**: Full cycle — user provides query, reviews plan, agents research in parallel, aggregation suggests gaps, user decides to refine or finish, final report exported as Markdown.

---

### Phase 5: Resumability & Polish

> **Goal**: Workflow persistence, resume capability, and UX polish.  
> **Deliverable**: Ability to resume interrupted runs, list past runs, and improved CLI output.

| Step | Description | Files | Requirements |
|------|-------------|-------|--------------|
| 5.1 | LangGraph checkpointer integration (SQLite or filesystem) | `workflow/orchestrator.py` | FR-7 |
| 5.2 | Resume workflow from checkpoint | `cli.py`, `workflow/` | FR-7 |
| 5.3 | `margre runs list` — list past runs with status | `cli.py`, `persistence/runs.py` | FR-7 |
| 5.4 | `margre runs show <id>` — display run details | `cli.py` | FR-7 |
| 5.5 | Logging and observability improvements | throughout | NFR-4 |
| 5.6 | Optional LangSmith tracing toggle | `config.py`, `llm/client.py` | NFR-4 |
| 5.7 | README, config.toml.example, final cleanup | project root | — |

**Demo**: Start a research run, interrupt it (Ctrl+C), resume with `margre resume <run-id>`, list all past runs.

---

## Neo4j Graph Schema (Initial)

```cypher
// Constraints
CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT source_url IF NOT EXISTS FOR (s:Source) REQUIRE s.url IS UNIQUE;

// Node types
// (:Person {name, birth_year, death_year, description, era, nationality})
// (:Event {name, date, description, location})
// (:Organisation {name, founded, description, type})
// (:Source {url, title, snippet, file_path, retrieved_at})
// (:ResearchRun {run_id, query, started_at, status})

// Relationship types
// (Person)-[:ALLIED_WITH {period, context}]->(Person)
// (Person)-[:RIVAL_OF {period, context}]->(Person)
// (Person)-[:INFLUENCED {domain}]->(Person)
// (Person)-[:MEMBER_OF {role, period}]->(Organisation)
// (Person)-[:PARTICIPATED_IN {role}]->(Event)
// (Person)-[:SOURCED_FROM]->(Source)
// (Event)-[:SOURCED_FROM]->(Source)
// (ResearchRun)-[:PRODUCED]->(Person|Event|Organisation)
```

---

## Configuration Template

```toml
[llm]
base_url = "http://localhost:1234/v1"   # OpenAI-compatible endpoint
api_key = ""                             # Or set via MARGRE_LLM_API_KEY env var
model = "default"
temperature = 0.7

[neo4j]
uri = "bolt://localhost:7687"
username = "neo4j"
password = ""                            # Or set via MARGRE_NEO4J_PASSWORD env var
database = "neo4j"

[search]
provider = "ddgs"                        # "ddgs" or "searxng"
max_results = 10

[search.searxng]
base_url = "http://localhost:8080"

[workflow]
max_research_loops = 3
max_agents_per_run = 5
output_dir = "./runs"

[logging]
level = "INFO"
```

---

## Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| LangGraph `Send` API limitations for dynamic agent count | May need to cap parallelism or restructure | Start with small agent counts (2-3), test scaling |
| Neo4j entity deduplication across runs | Stale or duplicate nodes | Use `MERGE` operations with unique constraints |
| LLM output format inconsistency | Parsing failures in planner/aggregator | Use structured output (JSON mode) with validation schemas |
| DDGS rate limiting | Search failures during high-throughput runs | Add retry logic, fallback to SearXNG |
| Workflow state corruption on unexpected exit | Lost progress | Phase 5 checkpointer addresses this |

---

## Phase Dependency Graph

```
Phase 1 (Foundation)
   │
   ▼
Phase 2 (Search & Persistence)
   │
   ▼
Phase 3 (Planning & Research)
   │
   ▼
Phase 4 (Aggregation & Reporting)
   │
   ▼
Phase 5 (Resumability & Polish)
```

All phases are sequential — each builds on the prior. Within each phase, steps can be partially parallelised where no dependency exists.
