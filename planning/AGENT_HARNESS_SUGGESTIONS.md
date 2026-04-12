# MARGRe — Agent Harness Suggestions

> **Context**: Analysis of the current MARGRe codebase and architecture to provide actionable suggestions for improving the multi-agent research harness.  
> **Date**: 2026-04-12

---

## 1. Architecture Overview (Current State)

MARGRe uses **LangGraph** with an orchestrator-worker pattern:

| Component | File | Role |
|-----------|------|------|
| Orchestrator | `workflow/orchestrator.py` | StateGraph: Plan → Dispatch → Research → Aggregate → Loop/End |
| Planner | `workflow/planner.py` | Decomposes seed person into search-oriented subtasks |
| Researcher | `workflow/researcher.py` | Web search → Synthesis → Relationship extraction → Neo4j persistence |
| Aggregator | `workflow/aggregator.py` | Merges agent outputs, deduplicates, identifies expansion candidates |
| HITL | `workflow/hitl.py` | Conditional routing based on `user_approved_plan` flag |
| State | `workflow/state.py` | `OrchestratorState` (top-level) + `ResearcherState` (per-subtask) |
| Prompts | `llm/prompts.py` | All prompt templates as string constants |
| LLM Client | `llm/client.py` | Singleton `ChatOpenAI` wrapper |

---

## 2. Prompt Management

### Current State
All prompts are raw string constants in `llm/prompts.py` with inline Python `.format()` substitution. This creates several pain points:
- **No versioning or A/B testing** — changing a prompt is a code change
- **Hard to tune** — no quick-edit capability without redeployment
- **Mixing of structure and content** — prompt engineering is entangled with Python code

### Suggestions

**2.1 Externalise prompts to YAML/TOML files**

Move all prompts out of `prompts.py` into per-node prompt files under `src/margre/llm/prompts/`:

```
llm/prompts/
├── planner_discovery.yaml
├── planner_refinement.yaml
├── planner_fallback.yaml
├── researcher_synthesis.yaml
├── researcher_extraction.yaml
├── aggregator_synthesis.yaml
└── aggregator_gaps.yaml
```

Each YAML file:
```yaml
system: |
  You are a social and professional network analyst...
human_template: |
  Discover connections for '{seed_person}'...
variables:
  - seed_person
  - known_entities
version: "1.0"
```

Add a `PromptLoader` class in `prompts.py` that reads from these files and caches them, falling back to inline defaults if files are missing. This allows prompt iteration without touching Python code.

**2.2 Add prompt metadata for observability**

Include `version` and `model_hint` in each prompt definition. Log the prompt version alongside each LLM invocation so you can trace which prompt version produced which result — essential for debugging agent quality.

---

## 3. LLM Client Hardening

### Current State
`llm/client.py` is a minimal singleton `get_model()` with a `create_completion()` helper. There's no retry logic, no token tracking, no structured output fallback at the client level.

### Suggestions

**3.1 Add retry with exponential backoff**

The researcher and planner nodes each handle structured output failures independently (manual JSON parsing fallback). Centralise this at the client level:

```python
# llm/client.py
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((RateLimitError, APIConnectionError, APITimeoutError))
)
def invoke_with_retry(model, messages, **kwargs):
    return model.invoke(messages, **kwargs)
```

Benefits:
- Remove duplicated fallback logic from `planner.py` and `researcher.py`
- Retry transient rate limits / timeouts automatically
- Consistent error handling across all nodes

**3.2 Streaming callback for progress**

The `ChatOpenAI` is initialised with `streaming=True`, but nothing consumes the stream. Add optional streaming callbacks to surface agent progress in the CLI:

```python
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
```

Enable via `--verbose` flag in the CLI and pipe through `rich.console` for colourised incremental output during long-running research.

**3.3 Token usage logging**

Log token counts per invocation. This is critical for cost tracking when using paid APIs (OpenRouter, etc.):

```python
response = model.invoke(messages, **kwargs)
logger.info(f"LLM: tokens_used={response.response_metadata.get('token_usage', {})}")
```

---

## 4. Researcher Node Improvements

### Current State
The researcher (`workflow/researcher.py`) does: search → synthesis → extraction → persistence. It runs as a single blocking call with no retry on search failures and no multi-source search aggregation.

### Suggestions

**4.1 Multi-query search per subtask**

Instead of a single `provider.search(subtask.research_query)`, expand each subtask into 2-3 search queries with slight variations (the planner already generates the search angle, but the researcher only uses one query). Add a `search_queries: List[str]` field to `DiscoveryTask` and aggregate/deduplicate results before synthesis.

```python
# In researcher_node:
all_results = []
for query in [subtask.research_query, f"{subtask.research_query} biography", f"{subtask.research_query} associations"]:
    all_results.extend(provider.search(query, max_results=3))
# Deduplicate by URL
seen_urls = set()
unique_results = [r for r in all_results if r.url not in seen_urls and not seen_urls.add(r.url)]
```

**4.2 Retry on empty search results**

Currently, if search returns nothing, the researcher returns a minimal empty dict. Instead, retry with a simplified query:

```python
if not search_results:
    # Retry with a simplified query (remove qualifiers)
    simplified = subtask.research_query.split(" - ")[0]  # strip qualifiers
    search_results = provider.search(simplified, max_results=5)
```

**4.3 Decouple extraction from persistence**

The researcher currently does extraction + Neo4j writes in one pass. Split these into distinct steps:
1. `extract()` returns structured data only
2. `persist()` handles Neo4j writes

This makes unit testing easier (you can test extraction without a running Neo4j instance) and allows for retry/rollback of persistence independently.

---

## 5. Orchestrator & Loop Semantics

### Current State
The `route_after_aggregation` decides between "expand" and "end". On expand, the CLI currently picks only the **first candidate** as the new seed. The `seed_person` is overwritten in the state, losing the original seed context.

### Suggestions

**5.1 Multi-select candidate expansion (minor UX improvement)**

Currently the CLI only picks `candidates[0]` as the next seed (`cli.py:231`). This is fine architecturally — `seed_person` *should* change each loop (the planner queries Neo4j for existing connections, so no context is lost). The small gap is that the user can't select multiple candidates for batch expansion in one session.

This is a **P2 UX polish**, not a P1 architectural flaw. The current single-pick flow works correctly for depth-first exploration. If you want breadth-first batch expansion, add a selection step:

```python
# In cli.py, replace single-pick with multi-select:
from rich.prompt import Confirm
selected = multi_select("Which candidates to expand?", candidates)
# Then loop or queue them for sequential research
```

An expansion queue in state is overkill unless you explicitly want breadth-first mode. For now, the depth-first single-pick is working as designed.

**5.2 HITL candidate multi-select**

See 5.1 — this is the same change. Currently the HITL after aggregation presents candidates and asks a yes/no question. Replacing the single-pick `candidates[0]` with a multi-select list is the concrete improvement.

**5.3 Loop depth guard — per-person, not global**

Currently `loop_count` is incremented every time the planner runs, regardless of how many hops from the original seed. Track depth per person instead:

```python
	person_depth: Dict[str, int]  # Maps person name → distance from original seed
```

This ensures a fair expansion budget regardless of how many branches exist.

---

## 6. Aggregator Improvements

### Current State
The aggregator does two things in one node: (1) synthesis into a master report and (2) expansion candidate filtering. It reads agent Markdown reports from disk and sends them to the LLM.

### Suggestions

**6.1 Separate synthesis and candidate selection into two nodes**

Split `aggregator_node` into:
- `synthesis_node` — produces the master Markdown report
- `expansion_node` — identifies and ranks expansion candidates

This lets you re-run candidate selection without re-synthesising the report, and makes HITL clearer (approve the report vs. approve the expansion list).

**6.2 Candidate ranking heuristics**

Currently candidates are ranked by mention frequency. Add more signals:
- **Neo4j degree centrality** — persons already connected to many nodes are more valuable to expand
- **Relationship type weighting** — `INFLUENCED` and `COLLABORATED_WITH` suggest stronger ties than `KNEW`
- **Temporal proximity** — persons active in the same period are more likely to yield rich connections

```python
def rank_candidates(candidates: List[str], connections: List[Dict]) -> List[str]:
    """Score and rank expansion candidates."""
    scores = {}
    for name in candidates:
        scores[name] = 0
        # Mention frequency (current)
        scores[name] += candidate_counts.get(name, 0) * 2
        # Already connected to seed → higher priority
        if name in known_entities:
            scores[name] += 5
        # Strong relationship types → higher priority
        for c in connections:
            if c["target_name"] == name and c["rel_type"] in ["INFLUENCED", "COLLABORATED_WITH"]:
                scores[name] += 3
    return sorted(candidates, key=lambda n: scores.get(n, 0), reverse=True)
```

---

## 7. Error Handling & Resilience

### Current State
Errors in the researcher are caught at the top level of the CLI's `_run_workflow()`. Individual node failures crash the entire graph run.

### Suggestions

**7.1 Per-agent error isolation**

Wrap the researcher node logic in a try/except that returns a graceful-empty result instead of propagating the exception:

```python
def researcher_node(state: ResearcherState) -> dict:
    try:
        # ... existing logic
    except SearchProviderError as e:
        logger.error(f"RESEARCHER [{agent_id}]: Search failed: {e}")
        return {"final_report": f"Search failed for {seed_person}", "structured_data": {}}
    except Exception as e:
        logger.error(f"RESEARCHER [{agent_id}]: Unexpected error: {e}")
        return {"discovered_persons": [], "agent_results": [{"agent_id": agent_id, "error": str(e)}]}
```

This lets the aggregator still produce results even if one agent fails.

**7.2 Checkpoint after each node**

LangGraph's checkpointer saves state at each node boundary. Ensure every node produces meaningful partial state so the workflow can resume from the last successful node rather than restarting entirely.

**7.3 Neo4j driver resilience**

The `graph/connection.py` uses a singleton driver that doesn't reconnect on failure. Add connection pooling and retry:

```python
from neo4j import GraphDatabase

def get_driver() -> Driver:
    global _driver
    if _driver is None:
        config = get_config()
        _driver = GraphDatabase.driver(
            config.neo4j.uri,
            auth=(config.neo4j.username, config.neo4j.password),
            max_connection_lifetime=3600,  # Reconnect every hour
            connection_acquisition_timeout=30,
        )
    return _driver
```

---

## 8. Observability & Debugging

### Current State
Logging uses Python's `logging` module with `rich.logging.RichHandler`. No LangSmith, no structured metrics, no per-run trace files.

### Suggestions

**8.1 Per-run trace logging**

Save a structured JSONL trace for each run:

```python
# persistence/trace.py
def trace_event(run_id: str, event: str, data: dict):
    trace_file = get_runs_dir() / run_id / "trace.jsonl"
    trace_file.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.utcnow().isoformat(), "event": event, **data}
    trace_file.open("a").write(json.dumps(entry) + "\n")
```

Call `trace_event()` at key points: plan generated, search executed, extraction completed, relationships persisted, aggregator synthesis done, etc. This creates an audit trail for debugging without requiring LangSmith.

**8.2 Optional LangSmith integration**

Add a config toggle:

```toml
[llm]
langsmith_enabled = false
langsmith_project = "margre"
```

When enabled, wrap the model with `langchain.callbacks.tracers.LangChainTracer`:

```python
if config.llm.langsmith_enabled:
    os.environ["LANGCHAIN_API_KEY"] = config.llm.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = config.llm.langsmith_project
```

**8.3 Agent-level timing metrics**

Track wall-clock time per agent (search, synthesis, extraction) and log it:

```python
start = time.monotonic()
search_results = provider.search(query, max_results=5)
search_time = time.monotonic() - start
logger.info(f"RESEARCHER [{agent_id}]: search took {search_time:.1f}s for {len(search_results)} results")
```

---

## 9. Configuration Enhancements

### Current State
`config.toml` covers LLM, Neo4j, search, and workflow settings. No per-model parameters, no per-node overrides.

### Suggestions

**9.1 Per-node model configuration**

Allow different models for different nodes (e.g., cheaper/faster model for planner, stronger model for extraction):

```toml
[llm]
base_url = "http://localhost:1234/v1"
model = "default"

[llm.nodes.planner]
model = "fast-model"

[llm.nodes.researcher]
model = "strong-model"

[llm.nodes.aggregator]
model = "strong-model"
```

Update `llm/client.py` to support `get_model(node: str) -> ChatOpenAI` with per-node overrides.

**9.2 Search configuration per angle**

Allow different search providers or result limits per search angle:

```toml
[search]
provider = "ddgs"
max_results = 5

[search.angles.collaborators]
max_results = 8

[search.angles.rivals]
max_results = 3
```

**9.3 Config validation**

Add a `validate_config()` function in `config.py` that checks for common issues:
- Neo4j password is not empty
- LLM base_url is a valid URL
- Search provider is one of `["ddgs", "searxng"]`
- `max_expansion_depth` is ≥ 1
- Output directory is writable

Call this during `margre init` and at workflow start.

---

## 10. Testing Strategy

### Current State
No tests exist yet. The planning docs mention `tests/` but the directory has no content.

### Suggestions

**10.1 Test structure mirroring**

```
tests/
├── conftest.py          # Shared fixtures (mock driver, mock model, temp runs dir)
├── test_config.py
├── test_search/
│   ├── test_ddgs.py
│   └── test_searxng.py
├── test_graph/
│   ├── test_repository.py
│   └── test_schema.py
├── test_workflow/
│   ├── test_planner.py
│   ├── test_researcher.py
│   └── test_aggregator.py
└── test_integration/
    └── test_discovery_e2e.py
```

**10.2 Key test cases**

| Component | Test | Approach |
|-----------|------|----------|
| `planner_node` | Generates valid `DiscoveryPlan` from seed | Mock LLM, assert subtask structure |
| `researcher_node` | Handles empty search results gracefully | Mock search provider returning `[]` |
| `researcher_node` | Extraction fallback works when structured output fails | Mock LLM returning non-JSON |
| `aggregator_node` | Deduplicates candidates correctly | Pre-populate Neo4j with test data |
| `repository.py` | `save_relationship` creates edges correctly | Neo4j test container |
| `config.py` | Loads and validates config.toml | Temp file fixture |
| `orchestrator.py` | Graph compiles and routes correctly | `graph.get_graph().print_ascii()` |

**10.3 Neo4j test container**

Use `testcontainers-python` for integration tests:

```python
# conftest.py
from testcontainers.neo4j import Neo4jContainer

@pytest.fixture(scope="session")
def neo4j_container():
    with Neo4jContainer("neo4j:5") as container:
        yield container
```

**10.4 Mock LLM responses**

Create a `MockModel` that returns pre-defined responses for each node type, enabling fast unit tests without an actual LLM endpoint:

```python
class MockModel:
    def invoke(self, messages, **kwargs):
        # Return canned responses based on prompt content
        if "discover" in messages[-1].content.lower():
            return MockResponse(content=MOCK_DISCOVERY_PLAN)
        elif "extract" in messages[-1].content.lower():
            return MockResponse(content=MOCK_EXTRACTION_RESULT)
```

---

## 11. CLI & UX

### Current State
CLI uses `typer` with `rich` for formatted output. The `discover` command handles the full workflow including HITL interrupts. No progress bars, no summary table at end.

### Suggestions

**11.1 Progress indicators**

Add `rich.progress` for search stages:

```python
from rich.progress import Progress

with Progress() as progress:
    task = progress.add_task("Researching...", total=len(plan.subtasks))
    for event in graph.stream(state, config, stream_mode="values"):
        progress.update(task, advance=1)
```

**11.2 End-of-run summary**

After the workflow completes, print a summary table:

```python
console.print(Panel.fit(
    f"[bold green]Discovery Complete[/bold green]\n"
    f"Persons discovered: {len(discovered_persons)}\n"
    f"Relationships saved: {total_rels}\n"
    f"Expansion candidates: {len(candidates)}\n"
    f"Report: {report_path}"
))
```

**11.3 `margre graph export` command**

Add a command to export the Neo4j subgraph as JSON or Mermaid:

```bash
margre graph export "Leonardo da Vinci" --format mermaid
margre graph export "Leonardo da Vinci" --format json
```

---

## 12. Priority Roadmap

| Priority | Item | Impact | Effort |
|----------|------|--------|--------|
| **P0** | Per-agent error isolation (7.1) | Prevents full workflow crash on single agent failure | Low |
| **P0** | Multi-query search / retry on empty (4.1, 4.2) | Direct quality improvement for research results | Low |
| **P0** | Config validation (9.3) | Prevents silent misconfig at runtime | Low |
| **P1** | Externalised prompts (2.1) | Enables rapid prompt iteration | Medium |
| **P1** | Per-node model config (9.1) | Cost optimisation for multi-model setups | Medium |
| **P1** | LLM retry with backoff (3.1) | Resilience against provider rate limits | Low |
| **P2** | Multi-select candidate expansion (5.1) | UX polish for breadth-first mode | Low |
| **P1** | Split aggregator into two nodes (6.1) | Cleaner HITL separation | Medium |
| **P2** | Per-run JSONL tracing (8.1) | Debugging and audit trail | Medium |
| **P2** | Candidate ranking heuristics (6.2) | Better expansion quality | Medium |
| **P2** | Test suite (10.x) | Long-term maintainability | High |
| **P2** | CLI progress & summary (11.1, 11.2) | UX polish | Low |
| **P3** | Streaming callbacks (3.2) | Real-time feedback during long runs | Medium |
| **P3** | Per-person depth tracking (5.3) | Fair expansion budgets | Low |
| **P3** | Graph export command (11.3) | Output flexibility | Low |
| **P3** | LangSmith integration (8.2) | Observability for production use | Medium |

---

## 13. Quick Wins (Can be done in < 1 day each)

1. **Add token usage logging** — 3 lines in `client.py`, huge visibility gain
2. **Retry on empty search** — 5 lines in `researcher.py`, immediate quality bump
3. **Config validation** — ~30 lines in `config.py`, prevents debug sessions
4. **Per-agent error isolation** — wrap researcher in try/except, return graceful empty
5. **End-of-run summary in CLI** — 10 lines in `_run_workflow()`, better UX

---

  Highest priority (P0):
  - Per-agent error isolation — currently a single researcher failure crashes the whole workflow
  - Multi-query search / retry on empty — single-query search misses too many results
  - Config validation — prevent silent misconfig at startup

  Key architectural suggestions:
  1. Externalise prompts to YAML — enables rapid prompt iteration without code changes
  2. Expansion queue instead of seed overwrite — the current approach loses original context and only expands the first candidate
  3. Split aggregator into synthesis + candidate selection — cleaner HITL and enables re-running candidate selection
  independently
  4. Per-node model configuration — use cheaper models for planner, stronger models for extraction
  5. LLM retry with backoff — centralised at the client level instead of duplicated per-node fallback logic

  Quick wins (< 1 day each):
  - Token usage logging (3 lines)
  - Empty search retry (5 lines)
  - Config validation (~30 lines)
  - Per-agent error try/except
  - End-of-run CLI summary