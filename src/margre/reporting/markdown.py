"""Report generation logic for synthesizer results."""

import logging
from pathlib import Path
from typing import Dict, Any

from margre.persistence.runs import get_runs_dir, save_run_metadata

logger = logging.getLogger(__name__)

def generate_final_report(run_id: str, master_report: str, metadata: Dict[str, Any]) -> str:
    """
    Saves the final synthesized report as a standalone Markdown file.
    """
    path = get_runs_dir() / run_id
    path.mkdir(parents=True, exist_ok=True)
    
    report_file = path / "final_report.md"
    
    # Enrich report with metadata header
    header = f"# MARGRe Research: {metadata.get('query', 'Unknown Topic')}\n"
    header += f"Run ID: `{run_id}` | Agents: {len(metadata.get('agents_involved', []))}\n\n---\n\n"
    
    full_content = header + master_report
    
    logger.info(f"REPORTING: Saving final Markdown report for run '{run_id}' to: {report_file}")
    report_file.write_text(full_content, encoding="utf-8")
    
    # Also update aggregation.json to track the report file path
    save_run_metadata(run_id, {"final_report_path": str(report_file.absolute())})
    
    return str(report_file.absolute())
