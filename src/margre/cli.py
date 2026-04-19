"""CLI entry point for MARGRe."""

import os
import shutil
import typer
from rich.console import Console
from rich.panel import Panel

from margre.config import load_config
from margre.graph.connection import verify_connection, close_driver
from margre.graph.schema import init_schema
from margre.search import get_search_provider
from margre.workflow.orchestrator import create_graph, get_checkpointer
from margre.health import check_readiness

import logging
from rich.logging import RichHandler

logger = logging.getLogger(__name__)


def setup_logging(level=logging.INFO):
    """Configure structured logging for MARGRe."""
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=Console(stderr=True))],
    )


app = typer.Typer(help="MARGRe — Multi-Agent Relation Graph Researcher")
console = Console()


@app.command()
def init():
    """Initialize the application configuration, checking Neo4j connection."""
    setup_logging()
    console.print("[bold green]Initializing MARGRe...[/bold green]")

    if not os.path.exists("config.toml"):
        if os.path.exists("config.toml.example"):
            shutil.copy("config.toml.example", "config.toml")
            console.print("[yellow]Created config.toml from example.[/yellow]")
        else:
            console.print("[bold red]Failed to find config.toml.example![/bold red]")
            raise typer.Exit(1)

    # Load config and verify Neo4j
    config = load_config()
    console.print("[blue]Configuration loaded.[/blue]")

    if verify_connection():
        console.print("[bold green]Successfully connected to Neo4j[/bold green]")

        # Initialize schema
        with console.status("[blue]Applying graph schema constraints...[/blue]"):
            results = init_schema()
            for r in results:
                if "Error" in r:
                    console.print(f"[red]{r}[/red]")
                else:
                    console.print(f"  [green]{r}[/green]")
    else:
        console.print("[bold red]Failed to connect to Neo4j. Is it running?[/bold red]")

    close_driver()

    console.print(
        Panel.fit(
            "[bold cyan]Initialization complete![/bold cyan]", border_style="green"
        )
    )


@app.command()
def chat(prompt: str):
    """Test standard LLM response using the wrapper."""
    setup_logging()
    if not check_readiness(check_llm=True, check_db=False):
        raise typer.Exit(1)

    try:
        from margre.llm.client import create_completion

        console.print(f"[bold cyan]User:[/bold cyan] {prompt}")
        with console.status("[blue]Generating completion...[/blue]"):
            messages = [{"role": "user", "content": prompt}]
            response = create_completion(messages)

        console.print(
            Panel(
                response,
                title="[bold green]Assistant[/bold green]",
                border_style="cyan",
            )
        )
    except Exception as e:
        console.print(f"[bold red]LLM test failed: {e}[/bold red]")
    finally:
        close_driver()


@app.command()
def search(query: str, limit: int = 5):
    """Test web search functionality."""
    setup_logging()
    # For a full system readiness check, require both LLM and DB
    if not check_readiness(check_llm=True, check_db=False):
        raise typer.Exit(1)

    console.print(f"[bold cyan]Search Query:[/bold cyan] {query}")
    try:
        provider = get_search_provider()
        with console.status(
            f"[blue]Searching using {provider.__class__.__name__}...[/blue]"
        ):
            results = provider.search(query, max_results=limit)

        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        for idx, r in enumerate(results, 1):
            console.print(f"\n[bold green]{idx}. {r.title}[/bold green]")
            console.print(f"   [dim]{r.url}[/dim]")
            console.print(f"   {r.snippet[:200]}...")
    except Exception as e:
        console.print(f"[bold red]Search failed: {e}[/bold red]")


@app.command()
def discover(
    seed_person: str, approve: bool = False, verbose: bool = False, thread_id: str = ""
):
    """Execute the multi-agent relationship discovery workflow."""
    setup_logging(level=logging.DEBUG if verbose else logging.INFO)
    if not check_readiness(check_llm=True, check_db=True):
        raise typer.Exit(1)

    if not thread_id:
        import uuid

        thread_id = str(uuid.uuid4())[:8]

    console.print(
        Panel(
            f"[bold cyan]Discovering Connections for:[/bold cyan] {seed_person}\n[dim]Thread ID: {thread_id}[/dim]",
            border_style="blue",
        )
    )

    from margre.workflow.orchestrator import create_graph, get_checkpointer

    with get_checkpointer() as checkpointer:
        graph = create_graph(checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        # Initial call
        initial_state = {
            "seed_person": seed_person,
            "messages": [],
            "plan": None,
            "agent_results": [],
            "discovered_persons": [],
            "loop_count": 0,
            "user_approved_plan": approve,
            "master_report": None,
            "suggested_gaps": [],
            "plan_revision_count": 0,
            "plan_revision_comments": None,
        }

        # Run until interrupt or completion
        _run_workflow(graph, initial_state, config, approve)


@app.command()
def resume(thread_id: str, approve: bool = False, verbose: bool = False):
    """Resume an existing discovery run by its thread ID."""
    setup_logging(level=logging.DEBUG if verbose else logging.INFO)
    if not check_readiness(check_llm=True, check_db=True):
        raise typer.Exit(1)

    console.print(
        Panel(
            f"[bold cyan]Resuming Thread:[/bold cyan] {thread_id}", border_style="blue"
        )
    )

    from margre.workflow.orchestrator import create_graph, get_checkpointer

    with get_checkpointer() as checkpointer:
        graph = create_graph(checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        # Check if thread exists
        state = graph.get_state(config)
        if not state or not state.values:
            console.print(
                f"[bold red]Thread '{thread_id}' not found in checkpoints![/bold red]"
            )
            return

        # Ensure new state fields are initialized on resume
        current_values = state.values
        if "plan_revision_count" not in current_values:
            graph.update_state(
                config, {"plan_revision_count": 0, "plan_revision_comments": None}
            )

        # Resume from where we left off
        _run_workflow(graph, None, config, approve)


def _run_workflow(graph, initial_state, config, initial_approve):
    """Helper to run the graph and handle interrupts."""
    try:
        current_state = initial_state

        while True:
            # 1. Stream values until interrupt
            last_event = None
            for event in graph.stream(current_state, config, stream_mode="values"):
                last_event = event

            # 2. Check current graph state
            graph_state = graph.get_state(config)
            next_nodes = graph_state.next
            state_values = graph_state.values

            if not next_nodes:
                console.print(
                    Panel.fit(
                        "[bold green]Discovery workflow completed![/bold green]",
                        border_style="green",
                    )
                )
                break

            # 3. Handle Planner Interrupt (Discovery Plan)
            if "research_dispatch_node" in next_nodes:
                plan = state_values.get("plan")
                if plan:
                    revision_count = state_values.get("plan_revision_count", 0)
                    if revision_count > 0:
                        console.print(
                            f"\n[bold green]Revised Discovery Plan for {plan.seed_person} (Revision {revision_count}):[/bold green]"
                        )
                    else:
                        console.print(
                            f"\n[bold green]Discovery Plan for {plan.seed_person} (Loop {state_values.get('loop_count')}):[/bold green]"
                        )
                    for idx, task in enumerate(plan.subtasks, 1):
                        console.print(
                            f"  {idx}. [bold cyan]{task.target_person}[/bold cyan] ({task.search_angle}): {task.research_query}"
                        )

                    if not initial_approve and not state_values.get(
                        "user_approved_plan"
                    ):
                        comment = typer.prompt(
                            "\nEnter comments on the plan (or press Enter to approve):",
                            default="",
                            show_default=False,
                        )
                        if comment.strip():
                            # User has feedback — save it and replan
                            console.print(
                                f"[dim]Revising plan with your feedback...[/dim]"
                            )
                            graph.update_state(
                                config,
                                {
                                    "plan_revision_comments": comment.strip(),
                                    "user_approved_plan": False,
                                },
                            )
                        else:
                            # Empty input = approve
                            graph.update_state(config, {"user_approved_plan": True})

                # Continue execution
                current_state = None
                continue

            # 4. Handle Candidate Interrupt (Expansion candidates)
            if "__end__" not in next_nodes:
                # If we stopped after candidate_node
                if state_values.get("master_report"):
                    console.print(
                        f"\n[bold green]Discovery Synthesis for {state_values.get('seed_person')}:[/bold green]"
                    )
                    preview = state_values.get("master_report")[:600] + "..."
                    console.print(
                        Panel(preview, title="Network Overview", border_style="green")
                    )

                    candidates = state_values.get("suggested_gaps", [])
                    if candidates:
                        console.print(
                            f"\n[bold yellow]Discovered Potential Candidates for Expansion ({len(candidates)}):[/bold yellow]"
                        )
                        for cand in candidates:
                            if isinstance(cand, dict):
                                console.print(
                                    f" • [bold cyan]{cand['name']}[/bold cyan] (score: {cand['score']:.1f})"
                                )
                            else:
                                console.print(
                                    f" • [bold cyan]{cand.name}[/bold cyan] (score: {cand.score:.1f})"
                                )

                        if typer.confirm(
                            "\nWould you like to expand the research to discover connections for these candidates?",
                            default=False,
                        ):
                            # For now, picking the first candidate as the new seed for the next loop
                            # (Advanced: could pick all or a subset)
                            first_cand = candidates[0]
                            if isinstance(first_cand, dict):
                                next_seed = first_cand["name"]
                            else:
                                next_seed = first_cand.name
                            console.print(
                                f"[blue]Expanding to discover connections for: {next_seed}[/blue]"
                            )
                            graph.update_state(
                                config,
                                {"seed_person": next_seed, "user_approved_plan": False},
                            )
                            current_state = None
                            continue

                    console.print(
                        "[blue]Discovery cycle complete. Final results saved to graph and filesystem.[/blue]"
                    )
                    break

    except Exception as e:
        console.print(f"[bold red]Workflow error: {e}[/bold red]")
        import traceback

        logger.debug(traceback.format_exc())
    finally:
        close_driver()


#
# Subcommands Group: graph
#
graph_app = typer.Typer(help="Query and inspect the relationships in Neo4j.")
app.add_typer(graph_app, name="graph")


@graph_app.command("show")
def graph_show(
    person: str,
    filter_label: str = typer.Option(
        None,
        "--filter",
        "-f",
        help="Filter by entity label (Person, Institution, Contribution, etc.)",
    ),
):
    """Show known connections for a given person in the terminal."""
    from margre.graph.repository import get_person_connections
    from rich.table import Table

    setup_logging()
    if not verify_connection():
        console.print("[bold red]Could not connect to Neo4j.[/bold red]")
        return

    connections = get_person_connections(person)

    if filter_label:
        connections = [
            c for c in connections if c["target_label"].lower() == filter_label.lower()
        ]

    if not connections:
        filter_msg = f" (filtered by {filter_label})" if filter_label else ""
        console.print(
            f"[yellow]No connections found for {person}{filter_msg} in the graph.[/yellow]"
        )
        return

    table = Table(title=f"Relationships for [bold cyan]{person}[/bold cyan]")
    table.add_column("Type", style="magenta")
    table.add_column("Target", style="cyan")
    table.add_column("Context", style="dim")
    table.add_column("Temporal", style="yellow")

    for c in connections:
        props = c.get("properties", {})
        temporal = f"{props.get('year', '')} {props.get('period', '')}".strip()
        table.add_row(
            c["rel_type"],
            f"{c['target_name']} ({c['target_label']})",
            props.get("context", ""),
            temporal,
        )

    console.print(table)
    close_driver()


#
# Subcommands Group: runs
#
runs_app = typer.Typer(help="Manage research runs and historical reports.")
app.add_typer(runs_app, name="runs")


@runs_app.command("list")
def runs_list():
    """List all completed or interrupted research runs."""
    from margre.persistence.runs import list_runs, read_run_metadata

    run_ids = list_runs()
    if not run_ids:
        console.print("[yellow]No research runs found.[/yellow]")
        return

    console.print("\n[bold cyan]Historical Research Runs:[/bold cyan]")
    for rid in run_ids:
        meta = read_run_metadata(rid)
        query = meta.get("query", "Unknown Query")
        # Find thread_id context if possible
        console.print(f" - [bold green]{rid}[/bold green]: {query}")


@runs_app.command("show")
def runs_show(run_id: str):
    """Show details and the final report path for a specific run."""
    from margre.persistence.runs import read_run_metadata

    meta = read_run_metadata(run_id)
    if not meta:
        console.print(f"[bold red]Run ID '{run_id}' not found.[/bold red]")
        return

    console.print(
        Panel(f"[bold cyan]Run Details:[/bold cyan] {run_id}", border_style="blue")
    )
    console.print(f"[bold green]Query:[/bold green] {meta.get('query')}")
    console.print(
        f"[bold green]Agents Contributed:[/bold green] {len(meta.get('agents_involved', []))}"
    )

    if meta.get("final_report_path"):
        console.print(
            f"[bold green]Final Report:[/bold green] [underline]{meta.get('final_report_path')}[/underline]"
        )

    if meta.get("master_report"):
        summary = meta.get("master_report")[:800] + "..."
        console.print("\n[bold cyan]Report Preview:[/bold cyan]")
        console.print(Panel(summary, border_style="green"))


@runs_app.command("report")
def runs_report(run_id: str):
    """Re-generate the HTML report, Mermaid graph, and Markdown report for a run."""
    from margre.persistence.runs import read_run_metadata, get_runs_dir
    import os

    meta = read_run_metadata(run_id)
    if not meta:
        console.print(f"[bold red]Run ID '{run_id}' not found.[/bold red]")
        raise typer.Exit(1)

    run_path = get_runs_dir() / run_id
    if not run_path.exists():
        console.print(f"[bold red]Run directory not found: {run_path}[/bold red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]Re-generating reports for run:[/bold cyan] {run_id}")

    # Re-generate Mermaid graph
    try:
        from margre.reporting.mermaid import save_mermaid

        mermaid_path = save_mermaid(run_id)
        console.print(f"  [green]Mermaid graph:[/green] {mermaid_path}")
    except Exception as e:
        console.print(f"  [red]Mermaid graph failed: {e}[/red]")

    # Re-generate HTML report
    try:
        from margre.reporting.html import save_html_report

        html_path = save_html_report(run_id)
        console.print(f"  [green]HTML report:[/green] {html_path}")
    except Exception as e:
        console.print(f"  [red]HTML report failed: {e}[/red]")

    console.print("[bold green]Done.[/bold green]")


if __name__ == "__main__":
    app()
