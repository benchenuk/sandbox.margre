"""Mermaid flowchart generation from agent structured JSON results."""

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from margre.persistence.runs import get_runs_dir

logger = logging.getLogger(__name__)

# Mermaid node shape conventions by entity label
NODE_SHAPES = {
    "Person": ("([", "])"),       # rounded/stadium
    "Institution": ("[", "]"),     # rectangle
    "Contribution":("[[", "]]"),   # subroutine (double rectangle)
    "Location": ("{{", "}}"),      # diamond-ish (hexagon)
    "Event": (">", "]"),          # asymmetric (flag)
    "Source": ("(", ")"),         # rounded
}

DEFAULT_SHAPE = ("[", "]")


def _mermaid_id(name: str) -> str:
    """Sanitise a name into a valid Mermaid node ID (no spaces, no special chars)."""
    return re.sub(r'[^a-zA-Z0-9_]', '_', name)


def _mermaid_label(name: str, extra: str = "") -> str:
    """Build a display label, truncating long names and appending extra info."""
    label = name
    if extra:
        label = f"{name}<br/>{extra}"
    # Escape quotes for Mermaid
    return label.replace('"', '&#quot;')


def _edge_label(rel_type: str, year: int | None, period: str | None) -> str:
    """Build an edge label from relationship type and temporal data."""
    parts = [rel_type]
    if year:
        parts.append(str(year))
    elif period:
        parts.append(period)
    return " ".join(parts)


def _deduplicate_relationships(
    relationships: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Merge duplicate relationships, keeping the one with the richest context."""
    seen: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for rel in relationships:
        key = (rel["rel_type"], rel["target_name"], rel.get("target_label", "Person"))
        existing = seen.get(key)
        if existing is None:
            seen[key] = rel
        else:
            # Keep the one with more context
            if len(rel.get("context", "")) > len(existing.get("context", "")):
                seen[key] = rel
            # Prefer the one with year info
            if rel.get("year") and not existing.get("year"):
                seen[key] = rel
    return list(seen.values())


def generate_mermaid(run_id: str) -> str:
    """Generate a Mermaid LR flowchart from the agent JSON results of a run.

    Reads all ``runs/<run_id>/agents/*.json`` files and the
    ``aggregation.json`` seed person, deduplicates relationships, and
    produces a left-to-right flowchart with edge labels for relationship
    types and temporal data.

    Returns:
        Mermaid flowchart source as a string.
    """
    runs_dir = get_runs_dir()
    run_path = runs_dir / run_id
    agents_path = run_path / "agents"

    # 1. Get seed person
    aggregation_path = run_path / "aggregation.json"
    seed_person = run_id  # fallback
    if aggregation_path.exists():
        try:
            meta = json.loads(aggregation_path.read_text(encoding="utf-8"))
            seed_person = meta.get("seed_person", seed_person)
        except Exception as e:
            logger.warning(f"MERMAID: Could not read aggregation.json: {e}")

    # 2. Collect all relationships from agent JSONs
    all_relationships: List[Dict[str, Any]] = []
    if agents_path.exists():
        for json_file in sorted(agents_path.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                all_relationships.extend(data.get("relationships", []))
            except Exception as e:
                logger.warning(f"MERMAID: Could not read {json_file.name}: {e}")

    if not all_relationships:
        logger.warning(f"MERMAID: No relationships found for run '{run_id}'")
        return f"graph LR\n    { _mermaid_id(seed_person)}[\"{seed_person}\"]\n"

    # 3. Deduplicate and filter self-edges (seed pointing to itself)
    relationships = _deduplicate_relationships(all_relationships)
    seed_id = _mermaid_id(seed_person)
    relationships = [r for r in relationships if _mermaid_id(r["target_name"]) != seed_id]

    # 4. Group relationships by type
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rel in relationships:
        by_type[rel["rel_type"]].append(rel)

    # 5. Build Mermaid flowchart with subgraphs per relationship type
    lines = [f"graph LR"]

    # Collect declared nodes to avoid duplicates
    declared_nodes: Dict[str, Tuple[str, str]] = {}  # id -> (shape_left, shape_right)

    # Seed person
    seed_shape = NODE_SHAPES.get("Person", DEFAULT_SHAPE)
    lines.append(f"    {seed_id}{seed_shape[0]}\"{_mermaid_label(seed_person)}\"{seed_shape[1]}")

    for rel_type, rels in by_type.items():
        subgraph_id = _mermaid_id(rel_type)
        lines.append(f"    subgraph {subgraph_id}[\"{rel_type}\"]")

        for rel in rels:
            target_id = _mermaid_id(rel["target_name"])
            if target_id not in declared_nodes:
                target_label = rel.get("target_label", "Person")
                shape = NODE_SHAPES.get(target_label, DEFAULT_SHAPE)
                declared_nodes[target_id] = shape
                lines.append(
                    f"        {target_id}{shape[0]}\"{_mermaid_label(rel['target_name'])}\"{shape[1]}"
                )
            label = _edge_label(rel["rel_type"], rel.get("year"), rel.get("period"))
            lines.append(f"        {seed_id} -->|\"{label}\"| {target_id}")

        lines.append("    end")
        lines.append("")

    return "\n".join(lines) + "\n"


def save_mermaid(run_id: str) -> str:
    """Generate and save a Mermaid flowchart file for a run.

    Returns:
        Absolute path to the saved ``.mmd`` file.
    """
    mermaid_content = generate_mermaid(run_id)
    run_path = get_runs_dir() / run_id
    run_path.mkdir(parents=True, exist_ok=True)

    output_file = run_path / "graph.mmd"
    output_file.write_text(mermaid_content, encoding="utf-8")
    logger.info(f"MERMAID: Saved flowchart for run '{run_id}' to {output_file}")

    return str(output_file.absolute())