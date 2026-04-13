"""Mermaid mindmap generation from agent structured JSON results."""

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from margre.persistence.runs import get_runs_dir

logger = logging.getLogger(__name__)


def _mermaid_id(name: str) -> str:
    """Sanitise a name into a valid Mermaid node ID (no spaces, no special chars)."""
    return re.sub(r'[^a-zA-Z0-9_]', '_', name)


def _mermaid_label(name: str) -> str:
    """Build a display label for a mindmap node, escaping parens for Mermaid."""
    return name.replace('"', '&#quot;').replace(" (", " –").replace("(", " –").replace(")", "")


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
    """Generate a Mermaid mindmap from the agent JSON results of a run.

    Reads all ``runs/<run_id>/agents/*.json`` files and the
    ``aggregation.json`` seed person, deduplicates relationships, and
    produces a mindmap grouped by relationship type with years appended
    to target names.

    Returns:
        Mermaid mindmap source as a string.
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
        return f"mindmap\n    ((\"{_mermaid_label(seed_person)}\"))\n"

    # 3. Deduplicate and filter self-edges (seed pointing to itself)
    relationships = _deduplicate_relationships(all_relationships)
    seed_id = _mermaid_id(seed_person)
    relationships = [r for r in relationships if _mermaid_id(r["target_name"]) != seed_id]

    # 4. Build Mermaid mindmap: seed -> rel_type -> "target (year)"
    lines = ["mindmap"]

    # Root: seed person
    lines.append(f"    ((\"{_mermaid_label(seed_person)}\"))")

    # Collect by rel_type; deduplicate targets per rel_type
    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rel in relationships:
        key = rel["rel_type"]
        # Deduplicate: keep richest temporal info per target per rel_type
        existing = next((r for r in by_type[key] if r["target_name"] == rel["target_name"]), None)
        if existing:
            if rel.get("year") and not existing.get("year"):
                by_type[key].remove(existing)
                by_type[key].append(rel)
        else:
            by_type[key].append(rel)

    # Sort rel_types alphabetically for stable output
    for rel_type in sorted(by_type.keys()):
        lines.append(f"        {rel_type}")
        for rel in sorted(by_type[rel_type], key=lambda r: r["target_name"]):
            year = rel.get("year") or rel.get("period")
            label = _mermaid_label(rel["target_name"])
            if year:
                label = f"{label} ({year})"
            lines.append(f'            ("{label}")')

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