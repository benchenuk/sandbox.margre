"""Single-page HTML report viewer for MARGRe research runs.

Generates a self-contained HTML file that renders the Mermaid relationship graph
and Markdown report client-side using mermaid.js and marked.js (loaded from CDN).
"""

import json
import logging
from pathlib import Path
from typing import List

from margre.persistence.runs import get_runs_dir, read_run_metadata
from margre.reporting.mermaid import generate_mermaid

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MARGRe: {title}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/marked@15/marked.min.js"></script>
  <style>
    :root {{
      --bg: #fafafa;
      --text: #1a1a1a;
      --accent: #2563eb;
      --border: #e2e8f0;
      --muted: #64748b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      max-width: 56rem;
      margin: 0 auto;
      padding: 2rem 1rem;
    }}
    header {{ margin-bottom: 2rem; }}
    header h1 {{ font-size: 1.75rem; margin-bottom: 0.25rem; }}
    header p {{ color: var(--muted); font-size: 0.875rem; }}
    nav {{
      display: flex;
      gap: 1.5rem;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--border);
      margin-bottom: 2rem;
    }}
    nav a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 500;
    }}
    nav a:hover {{ text-decoration: underline; }}
    section {{ margin-bottom: 3rem; }}
    section h2 {{
      font-size: 1.25rem;
      margin-bottom: 1rem;
      padding-bottom: 0.5rem;
      border-bottom: 2px solid var(--accent);
      display: inline-block;
    }}
    .mermaid {{
      background: #fff;
      border: 1px solid var(--border);
      border-radius: 0.5rem;
      padding: 1.5rem;
      overflow-x: auto;
    }}
    #report-content {{ line-height: 1.7; }}
    #report-content h1 {{ font-size: 1.5rem; margin: 1.5rem 0 0.5rem; }}
    #report-content h2 {{ font-size: 1.25rem; margin: 1.25rem 0 0.5rem; }}
    #report-content h3 {{ font-size: 1.1rem; margin: 1rem 0 0.25rem; }}
    #report-content p {{ margin: 0.5rem 0; }}
    #report-content ul, #report-content ol {{
      margin: 0.5rem 0 0.5rem 1.5rem;
    }}
    #report-content hr {{ border: none; border-top: 1px solid var(--border); margin: 1rem 0; }}
    .files-list {{
      list-style: none;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
      gap: 0.5rem;
    }}
    .files-list li a {{
      display: block;
      padding: 0.5rem 0.75rem;
      background: #fff;
      border: 1px solid var(--border);
      border-radius: 0.375rem;
      color: var(--accent);
      text-decoration: none;
      font-size: 0.875rem;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .files-list li a:hover {{
      background: var(--accent);
      color: #fff;
    }}
    .agent-label {{
      font-size: 0.75rem;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <p>Run <code>{run_id}</code> &middot; {agent_count} agents</p>
  </header>

  <nav>
    <a href="#graph">Graph</a>
    <a href="#report">Report</a>
    <a href="#files">Files</a>
  </nav>

  {graph_section}

  <section id="report">
    <h2>Research Report</h2>
    <div id="report-content"></div>
  </section>

  <script id="report-md" type="text/markdown">{report_content}</script>

  <section id="files">
    <h2>Run Files</h2>
    <ul class="files-list">
{files_list}
    </ul>
  </section>

  <script>
    // Render Markdown report
    document.getElementById('report-content').innerHTML =
      marked.parse(document.getElementById('report-md').textContent);
    // Initialize Mermaid
    mermaid.initialize({{ startOnLoad: true }});
  </script>
</body>
</html>"""


def _build_graph_section(mermaid_source: str) -> str:
    """Build the Mermaid graph section HTML."""
    return (
        '<section id="graph">\n'
        '    <h2>Relationship Graph</h2>\n'
        f'    <div class="mermaid">\n{mermaid_source}\n    </div>\n'
        '</section>\n'
    )


def _build_files_list(run_path: Path, agent_ids: List[str]) -> str:
    """Build the file links section as HTML list items."""
    items = []
    items.append(
        '      <li><a href="aggregation.json">aggregation.json</a></li>'
    )
    if (run_path / "final_report.md").exists():
        items.append(
            '      <li><a href="final_report.md">final_report.md</a></li>'
        )
    if (run_path / "graph.mmd").exists():
        items.append(
            '      <li><a href="graph.mmd">graph.mmd</a></li>'
        )
    for agent_id in agent_ids:
        json_file = f"agents/{agent_id}.json"
        md_file = f"agents/{agent_id}.md"
        if (run_path / json_file).exists():
            items.append(
                f'      <li><a href="{json_file}">{agent_id}.json</a></li>'
            )
        if (run_path / md_file).exists():
            items.append(
                f'      <li><a href="{md_file}">{agent_id}.md</a></li>'
            )
    return "\n".join(items)


def generate_html_report(run_id: str) -> str:
    """Generate a self-contained HTML report viewer for a run.

    Client-side rendering: marked.js for Markdown, mermaid.js for the graph.
    All rendering happens in the browser — the HTML embeds raw content.

    Returns:
        HTML string.
    """
    runs_dir = get_runs_dir()
    run_path = runs_dir / run_id

    # 1. Read metadata
    meta = read_run_metadata(run_id)
    seed_person = meta.get("seed_person", run_id)
    agent_ids = meta.get("agents_involved", [])
    title = seed_person

    # 2. Read final report Markdown
    report_path = run_path / "final_report.md"
    report_content = ""
    if report_path.exists():
        report_content = report_path.read_text(encoding="utf-8")

    # 3. Generate Mermaid graph (skip if only a bare seed node with no edges)
    graph_section = ""
    try:
        mermaid_source = generate_mermaid(run_id)
        if mermaid_source.strip() and "-->" in mermaid_source:
            graph_section = _build_graph_section(mermaid_source)
    except Exception as e:
        logger.warning(f"HTML_REPORT: Could not generate Mermaid graph: {e}")

    # 4. Build file links
    files_list = _build_files_list(run_path, agent_ids)

    # 5. Assemble HTML
    html = HTML_TEMPLATE.format(
        title=title,
        run_id=run_id,
        agent_count=len(agent_ids),
        graph_section=graph_section,
        report_content=report_content,
        files_list=files_list,
    )
    return html


def save_html_report(run_id: str) -> str:
    """Generate and save an HTML report file for a run.

    Returns:
        Absolute path to the saved report.html file.
    """
    html_content = generate_html_report(run_id)
    run_path = get_runs_dir() / run_id
    run_path.mkdir(parents=True, exist_ok=True)

    output_file = run_path / "report.html"
    output_file.write_text(html_content, encoding="utf-8")
    logger.info(f"HTML_REPORT: Saved report for run '{run_id}' to {output_file}")

    return str(output_file.absolute())