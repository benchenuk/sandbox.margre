"""Run metadata and structured results persistence."""

import json
from pathlib import Path
from typing import Any, Dict

def get_runs_dir() -> Path:
    """Get the base runs directory, ensuring it exists."""
    from margre.config import get_config
    config = get_config()
    runs_dir = Path(config.workflow.output_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir

def save_run_metadata(run_id: str, data: Dict[str, Any]) -> str:
    """Save structured run metadata (JSON) to the filesystem."""
    path = get_runs_dir() / run_id
    path.mkdir(parents=True, exist_ok=True)
    
    file_path = path / "aggregation.json"
    
    # Simple merge if it already exists
    if file_path.exists():
        try:
            existing = json.loads(file_path.read_text(encoding="utf-8"))
            existing.update(data)
            data = existing
        except json.JSONDecodeError:
            pass
            
    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(file_path.absolute())

def save_agent_structured_result(run_id: str, agent_id: str, data: Dict[str, Any]) -> str:
    """Save an individual agent's structured JSON results."""
    path = get_runs_dir() / run_id / "agents"
    path.mkdir(parents=True, exist_ok=True)
    
    file_path = path / f"{agent_id}.json"
    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(file_path.absolute())

def read_run_metadata(run_id: str) -> Dict[str, Any]:
    """Read run metadata."""
    file_path = get_runs_dir() / run_id / "aggregation.json"
    if file_path.exists():
        return json.loads(file_path.read_text(encoding="utf-8"))
    return {}
