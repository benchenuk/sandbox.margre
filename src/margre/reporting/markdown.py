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
    topic = metadata.get('seed_person') or metadata.get('query') or 'Unknown'
    header = f"# MARGRe Discovery: {topic}\n"
    header += f"Run ID: `{run_id}` | Agents: {len(metadata.get('agents_involved', []))}\n\n---\n\n"
    
    full_content = header + master_report
    
    logger.info(f"REPORTING: Saving final Markdown report for run '{run_id}' to: {report_file}")
    report_file.write_text(full_content, encoding="utf-8")
    
    # Also update aggregation.json to track the report file path
    metadata_update = {"final_report_path": str(report_file.absolute())}

    # Generate Mermaid flowchart alongside the report
    from margre.reporting.mermaid import save_mermaid
    try:
        mermaid_path = save_mermaid(run_id)
        metadata_update["graph_path"] = mermaid_path
    except Exception as e:
        logger.warning(f"REPORTING: Failed to generate Mermaid flowchart: {e}")

    # Generate single-page HTML report
    from margre.reporting.html import save_html_report
    try:
        html_path = save_html_report(run_id)
        metadata_update["html_report_path"] = html_path
    except Exception as e:
        logger.warning(f"REPORTING: Failed to generate HTML report: {e}")

    save_run_metadata(run_id, metadata_update)

    return str(report_file.absolute())
