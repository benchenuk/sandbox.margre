# Candidate Ranking & Expansion Design

> Design for improving candidate selection at the end of each workflow iteration.
> Built on existing `DISCOVERY_PLAN.md` and `AGENT_HARNESS_SUGGESTIONS.md`.

---

## High-Level Overview

The current expansion loop has fundamental limitations:

| Current Behavior | Problem |
|---|---|
| Single-seed expansion | Only `candidates[0]` is used; all other candidates discarded |
| Frequency-only ranking | `Counter.most_common()` ignores relationship semantics |
| Global depth limit | `loop_count` applies to all persons equally, not per-person |
| Monolithic aggregator | Synthesis + candidate selection coupled in one node |

**New design** introduces:

1. **LLM-driven scoring** — Researchers score each new person (1-10) based on relationship impact
2. **Per-person depth tracking** — BFS expansion with depth limits per candidate
3. **Expansion queue** — Candidates accumulate across iterations, sorted by score
4. **Multi-select HITL** — User selects from ranked candidates with justifications

---

## Architecture

### State Model

```python
class NewPerson(BaseModel):
    name: str
    impact_score: float        # LLM-assigned 1-10
    impact_justification: str # Why this person matters
    relationship_context: str # How they connect to seed


class Candidate(BaseModel):
    name: str
    score: float               # Final consolidated score
    justification: str        # Combined reasoning
    depth: int                 # BFS depth from original seed


class OrchestratorState(TypedDict):
    # ... existing fields ...

    # New fields for expansion
    suggested_gaps: List[Candidate]                    # Per-loop candidates
    expansion_queue: Annotated[List[Candidate], add]  # Accumulated across loops
    explored_persons: Annotated[List[str], add]       # Seeds already used
    person_depth: Dict[str, int]                       # Per-person depth tracking
```

### Workflow Graph

```
START → planner_node → research_dispatch_node → (fan-out) researcher_node
                                        ↓
                                   aggregator_node
                                        ↓
                                  synthesis_node      # Master report
                                        ↓
                                  candidate_node      # Score & rank candidates
                                        ↓
                              [route_after_candidate] ← interrupt for HITL
                                        ↓
                              expansion_queue       # Next seed selected
                                        ↓
                              planner_node           # Loop
                                        ↓
                                        END
```

Key changes:
- `aggregator_node` split into `synthesis_node` + `candidate_node`
- Interrupt after `candidate_node` (replaces interrupt after `aggregator_node`)
- Routing: `synthesis_node → candidate_node → (expand | end)`

### Scoring Pipeline

```
Researcher Agent (per subtask)
├── Extracts relationships from web synthesis
└── For each NEW person discovered:
    ├── impact_score: 1-10 (LLM-assigned)
    ├── impact_justification: brief reasoning
    └── relationship_context: how they connect to seed

candidate_node (after synthesis)
├── Collect all NewPerson from all researchers
├── Deduplicate by name
├── For duplicate persons:
│   ├── Average the impact_score
│   └── Add small multiplicity bonus (+0.1 per additional mention)
├── Sort by final score descending
├── Filter: exclude if person_exists in Neo4j
├── Cap at max_candidates_per_loop
└── Return List[Candidate] as suggested_gaps
```

**No extra LLM call for reconciliation** — combining scores is arithmetic, not inference.

---

## Configuration

```toml
[workflow]
max_expansion_depth = 3      # Max BFS depth per candidate
max_candidates_per_loop = 5  # Candidates shown to user per iteration
```

---

## Implementation Iterations

### Iteration 1 — Architecture Split

- [ ] Split `aggregator_node` → `synthesis_node` + `candidate_node`
- [ ] Update orchestrator edges: `synthesis_node → candidate_node`
- [ ] Add `Candidate` model to `state.py`
- [ ] Change `suggested_gaps: List[str]` → `List[Candidate]`
- [ ] Move interrupt to after `candidate_node`
- [ ] Candidate node uses frequency ranking for now (straight refactor)

### Iteration 2 — Researcher-Level LLM Scoring

- [ ] Extend `DiscoveryExtractionResult.new_persons` from `List[str]` → `List[NewPerson]`
- [ ] Add `NewPerson` model to `state.py`
- [ ] Update `RELATIONSHIP_EXTRACTION_PROMPT` to instruct LLM scoring
- [ ] Update researcher to return enriched `new_persons` with scores
- [ ] Update `candidate_node` reconciliation: average + multiplicity bonus
- [ ] Keep Neo4j dedup procedural

### Iteration 3 — BFS Expansion Queue

- [ ] Add `expansion_queue`, `explored_persons`, `person_depth` to state
- [ ] Replace global `loop_count` usage with `person_depth` logic
- [ ] Update `route_after_candidate` to drain queue
- [ ] CLI multi-select: show ranked candidates with scores/justifications
- [ ] User picks one or more → enqueue for expansion

### Iteration 4 — Config, Tests & Polish

- [ ] Add `max_expansion_depth`, `max_candidates_per_loop` to config
- [ ] Unit tests for `candidate_node` scoring logic
- [ ] Unit tests for BFS queue management
- [ ] Unit tests for reconciliation (average + bonus)
- [ ] Update `TODO.md` with completed items

---

## Scoring Heuristics (Reference)

Initial prompt guidance for researcher LLM:

| Relationship Type | Expected Impact | Rationale |
|---|---|---|
| `COLLABORATED_WITH` | High (8-10) | Direct partnership, shared work |
| `STUDIED_AT` / `WORKED_AT` | High (7-9) | Structured relationship, institutions |
| `INFLUENCED` | Medium-High (6-8) | Intellectual impact |
| `OPPOSED` / `CRITIQUED` | Medium (5-7) | Active engagement, significance |
| `MENTOR` / `PROTÉGÉ` | High (8-10) | Career-shaping relationship |
| `RIVAL` | Medium-High (6-8) | Competition driving outcomes |
| `KNEW` | Low-Medium (3-5) | Vague, weak connection |
| `MEMBER_OF` | Low (2-4) | Affiliation, less personal |
| `LIVED_IN` | Low (1-3) | Geographic, weak |
| `(unknown)` | Default (4) | Fallback |

The LLM should adjust based on context (period, historical significance, etc.).

---

## Open Questions

- Should the multiplicity bonus be configurable?
- Should we include recency bias (candidates discovered more recently rank higher)?
- Should we allow the user to override LLM scores in the CLI?

---

## Related Documents

- `planning/DISCOVERY_PLAN.md` — Original discovery workflow design
- `planning/AGENT_HARNESS_SUGGESTIONS.md` — Prior suggestions for aggregator improvements
- `planning/TODO.md` — Task tracking
- `src/margre/workflow/aggregator.py` — Current implementation (to be split)
- `src/margre/workflow/state.py` — State models (to be extended)