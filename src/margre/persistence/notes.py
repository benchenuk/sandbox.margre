"""Filesystem persistence for research notes and workflow artifacts."""

import os
from pathlib import Path
from typing import Optional

import logging

logger = logging.getLogger(__name__)

def get_runs_dir() -> Path:
    """Get the base runs directory, ensuring it exists."""
    from margre.config import get_config
    config = get_config()
    runs_dir = Path(config.workflow.output_dir)
    if not runs_dir.exists():
        logger.info(f"PERSISTENCE: Creating runs directory at: {runs_dir}")
        runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir

def save_research_note(run_id: str, agent_id: str, content: str) -> str:
    """
    Save agent research notes to the filesystem as Markdown.
    Returns the absolute file path.
    """
    path = get_runs_dir() / run_id / "agents"
    path.mkdir(parents=True, exist_ok=True)
    
    file_path = path / f"{agent_id}.md"
    logger.info(f"PERSISTENCE: Saving research note for agent '{agent_id}' to: {file_path}")
    logger.debug(f"PERSISTENCE: Writing {len(content)} characters to {file_path}")
    file_path.write_text(content, encoding="utf-8")
    
    return str(file_path.absolute())

def read_research_note(run_id: str, agent_id: str) -> Optional[str]:
    """Read research note from the filesystem."""
    file_path = get_runs_dir() / run_id / "agents" / f"{agent_id}.md"
    if file_path.exists():
        logger.debug(f"PERSISTENCE: Reading research note from: {file_path}")
        return file_path.read_text(encoding="utf-8")
    logger.warning(f"PERSISTENCE: Research note not found for agent '{agent_id}' at: {file_path}")
    return None
