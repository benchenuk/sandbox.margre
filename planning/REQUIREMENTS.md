# MARGRe — Multi-Agent Relation Graph Researcher

A CLI-based multi-agent AI research tool focused on building relational graphs of historical personalities.

---

## Vision

Given a research topic (e.g., "The political alliances of Renaissance Italy"), MARGRe autonomously:
1. Plans the research scope and decomposes it into subtasks
2. Spawns specialist agents to investigate individual persons and relationships
3. Searches the web to gather evidence
4. Persists findings into a Neo4j graph database as entities and relationships
5. Aggregates, cross-references, and presents findings for human review
6. Iterates based on human feedback to deepen or redirect research

---

## Core Workflow

```
┌──────────────────────────────────────────────────────────────┐
│                         USER QUERY                           │
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│  1. PLAN — Orchestrator decomposes the query into subtasks   │
│     • Identifies historical persons (events, works,          | 
|       orgnisations) to research                              │
│     • Defines relationships to investigate                   │
│     • Produces a research plan for human approval (HITL)     │
└──────────────┬───────────────────────────────────────────────┘
               ▼  (Human approves / adjusts plan)
┌──────────────────────────────────────────────────────────────┐
│  2. RESEARCH — Dynamically spawned sub-agents                │
│     • Each agent focuses on a person or relationship cluster │
│     • Web search (DDGS / SearXNG) for evidence gathering     │
│     • Persist per-agent findings (Markdown notes + JSON)     │
└──────────────┬───────────────────────────────────────────────┘
               ▼
┌──────────────────────────────────────────────────────────────┐
│  3. AGGREGATE — Merge results into the knowledge graph       │
│     • Write structured data to Neo4j                         │
│     • Resolve duplicates and contradictions                  │
│     • Suggest new relationships or research gaps             │
│     • Present summary for human review (HITL)                │
└──────────────┬───────────────────────────────────────────────┘
               ▼  (Human reviews / decides next action)
┌──────────────────────────────────────────────────────────────┐
│  4. LOOP or EXIT                                             │
│     • Refine research (back to step 1 with new sub-queries)  │
│     • Export final report(s) as Markdown                     │
└──────────────────────────────────────────────────────────────┘
```

---

## Functional Requirements

### FR-1: Research Workflow Engine
- Repeatable, resumable workflow using LangGraph
- Workflow state persisted (via LangGraph checkpointer or Neo4j)
- Support for branching (parallel agent execution) and iterative looping

### FR-2: Dynamic Agent Creation
- Orchestrator agent plans and spawns research sub-agents dynamically
- Uses LangGraph's `Send` API or supervisor pattern for dynamic dispatch
- Each sub-agent operates on a scoped subtask (e.g., "research Machiavelli's political allies")
- Sub-agents have access to web search tools

### FR-3: Human-in-the-Loop (HITL)
- Pause workflow at defined checkpoints for human review
- Human can approve, modify, or reject the plan/results via CLI prompts
- HITL points: after planning (step 1) and after aggregation (step 3)

### FR-4: Knowledge Graph (Neo4j)
- **Node types**: `Person` (core), `Event`, `Organization`, `Source`
- **Relationship types**: `ALLIED_WITH`, `RIVAL_OF`, `INFLUENCED`, `PARTICIPATED_IN`, `MEMBER_OF`, `SOURCED_FROM`, etc.
- Person-centric schema — historical persons are the primary focus
- Support Cypher queries for aggregation and reporting
- Neo4j hosted locally (Docker or Neo4j Desktop — setup as part of development)

### FR-5: Web Search Integration
- Pluggable search provider interface
- Supported providers:
  - **DuckDuckGo (DDGS)** — via `duckduckgo-search` / `langchain_community`
  - **SearXNG** — via REST API to a self-hosted instance
- Search results cited and linked to graph entities via `Source` nodes

### FR-6: Aggregation & Reporting
- Cross-reference findings from multiple agents
- Detect duplicates and contradictions in the graph
- Generate final report(s) as **Markdown** files
- Attach **JSON** metadata for workflow states, citations, and structured data

### FR-7: Persistence & Resumability
- All workflow steps and intermediate results persisted
- Research notes stored as Markdown files on the filesystem
- Structured results stored as JSON
- Ability to resume a workflow from the last checkpoint
- Historical runs queryable for cross-session aggregation

---

## Non-Functional Requirements

### NFR-1: CLI Interface
- Simple CLI using `click` or `typer`
- No TUI framework — rely on terminal, filesystem, and Neo4j Browser for interaction
- Color-highlighted output for readability (via `rich` for printing/formatting)
- Clear progress indicators during agent execution

### NFR-2: Configuration
- TOML-based configuration (`config.toml`)
- Settings: LLM endpoint/model, Neo4j connection, search provider, output paths
- Example config template (`config.toml.example`) committed to repo
- Secrets via environment variables (never hardcoded)

### NFR-3: LLM Integration
- Use **OpenAI-compatible API** (not coupled to any specific provider)
- Works with any OpenAI-like endpoint
- Model and endpoint configurable in `config.toml`

### NFR-4: Observability
- Structured logging via Python `logging` with sensible levels
- Optional LangSmith integration for LLM call tracing

### NFR-5: Extensibility
- Pluggable search providers (interface + implementations)
- Pluggable LLM backends (via OpenAI-compatible API)
- Graph schema is evolvable (new node/relationship types addable)

---

## Technology Stack

| Layer            | Technology                                           |
|------------------|------------------------------------------------------|
| Language         | Python 3.11+                                         |
| Agent Framework  | LangGraph                                            |
| LLM             | OpenAI-compatible API (OpenRouter / LM Studio / etc.) |
| Graph Database   | Neo4j (local, via Docker or Neo4j Desktop)           |
| Web Search       | DuckDuckGo (`duckduckgo-search`), SearXNG            |
| CLI Framework    | `click` or `typer` + `rich` for formatting           |
| Config           | TOML (`tomllib`)                                     |
| Package Manager  | `uv`                                                 |
| Content Format   | Markdown (reports) + JSON (metadata)                 |
| Testing          | `pytest`                                             |

---

## References
- [Gemini Fullstack LangGraph Quickstart](https://github.com/google-gemini/gemini-fullstack-langgraph-quickstart)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [LangGraph Multi-agent Patterns](https://langchain.com/blog/multi-agent-workflows)
