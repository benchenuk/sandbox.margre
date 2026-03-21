# MARGRe — Multi-Agent Relation Graph Researcher

A CLI-based multi-agent AI research tool focused on building relational graphs of historical personalities.

---

## Getting Started

### Prerequisites

- **Python**: 3.12+ (managed with `uv`)
- **Database**: [Neo4j](https://neo4j.com/download/) (via Docker)
- **LLM Provider**: Any OpenAI-compatible endpoint (e.g., LM Studio, OpenRouter, LiteLLM)

### 1. Initial Setup

Install the dependencies and initialize the virtual environment:

```bash
uv sync
```

### 2. Start Neo4j

Start the local Neo4j instance using the provided Docker script:

```bash
./docker_neo4j.sh
```
*Wait for Neo4j to be healthy at `http://localhost:7474`.*

### 3. Initialize MARGRe

Create your configuration and apply the database schema (constraints):

```bash
uv run margre init
```
This will create a `config.toml` file. Edit it to match your LLM provider's `base_url`, `api_key`, and `model`.

---

## Basic Commands

### Verify LLM Connection

Test your LLM provider's response:
```bash
uv run margre chat "Hello, are you online?"
```

### Run Tests

Execute unit and integration tests:
```bash
uv run pytest
```

---

## Project Structure

- `src/margre/`: Core application logic (CLI, LLM client, Graph repository, Workflow)
- `tests/`: Unit and integration tests
- `runs/`: Output for research tasks (Markdown & JSON)
- `planning/`: Project requirements and implementation plans

---

## Reference

- [REQUIREMENTS.md](planning/REQUIREMENTS.md): Detailed functional and non-functional requirements.
- [IMPLEMENTATION_PLAN.md](planning/IMPLEMENTATION_PLAN.md): Phased development roadmap.
