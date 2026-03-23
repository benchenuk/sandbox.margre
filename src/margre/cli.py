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
        handlers=[RichHandler(rich_tracebacks=True, console=Console(stderr=True))]
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
    
    console.print(Panel.fit("[bold cyan]Initialization complete![/bold cyan]", border_style="green"))


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
            
        console.print(Panel(response, title="[bold green]Assistant[/bold green]", border_style="cyan"))
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
        with console.status(f"[blue]Searching using {provider.__class__.__name__}...[/blue]"):
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
def research(query: str, approve: bool = False, verbose: bool = False, thread_id: str = ""):
    """Execute the multi-agent research workflow."""
    setup_logging(level=logging.DEBUG if verbose else logging.INFO)
    if not check_readiness(check_llm=True, check_db=True):
        raise typer.Exit(1)
         
    if not thread_id:
        import uuid
        thread_id = str(uuid.uuid4())[:8]
        
    console.print(Panel(f"[bold cyan]Researching:[/bold cyan] {query}\n[dim]Thread ID: {thread_id}[/dim]", border_style="blue"))
    
    from margre.workflow.orchestrator import create_graph, get_checkpointer
    
    with get_checkpointer() as checkpointer:
        graph = create_graph(checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        
        # Initial call
        initial_state = {
            "query": query,
            "messages": [],
            "plan": None,
            "agent_results": [],
            "loop_count": 0,
            "user_approved_plan": approve,
            "master_report": None,
            "suggested_gaps": []
        }
        
        # Run until interrupt or completion
        _run_workflow(graph, initial_state, config, approve)

@app.command()
def resume(thread_id: str, approve: bool = False, verbose: bool = False):
    """Resume an existing research run by its thread ID."""
    setup_logging(level=logging.DEBUG if verbose else logging.INFO)
    if not check_readiness(check_llm=True, check_db=True):
        raise typer.Exit(1)
        
    console.print(Panel(f"[bold cyan]Resuming Thread:[/bold cyan] {thread_id}", border_style="blue"))
    
    from margre.workflow.orchestrator import create_graph, get_checkpointer
    
    with get_checkpointer() as checkpointer:
        graph = create_graph(checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        
        # Check if thread exists
        state = graph.get_state(config)
        if not state or not state.values:
            console.print(f"[bold red]Thread '{thread_id}' not found in checkpoints![/bold red]")
            return
            
        # Resume from where we left off
        _run_workflow(graph, None, config, approve)

def _run_workflow(graph, initial_state, config, initial_approve):
    """Helper to run the graph and handle interrupts."""
    try:
        # If initial_state is None, it resumes
        current_state = initial_state
        
        while True:
            # Run until next interrupt or end
            for event in graph.stream(current_state, config, stream_mode="values"):
                # We can log state values here if needed
                pass
            
            # Check why we stopped
            graph_state = graph.get_state(config)
            next_nodes = graph_state.next
            
            if not next_nodes:
                # Reached END
                console.print(Panel.fit("[bold green]Workflow completed![/bold green]", border_style="green"))
                break
            
            # 1. Planner Interrupt (Approval)
            if "research_dispatch_node" in next_nodes or "planner_node" in next_nodes:
                # Check if we need approval
                state_values = graph_state.values
                plan = state_values.get("plan")
                
                if plan:
                    console.print(f"\n[bold green]Research Plan Generated (Loop {state_values.get('loop_count')}):[/bold green]")
                    for idx, task in enumerate(plan.subtasks, 1):
                        console.print(f"  {idx}. [cyan]{task.entity_name}[/cyan] ({task.entity_type}): {task.research_query}")
                    
                    if not initial_approve and not state_values.get("user_approved_plan"):
                        if not typer.confirm("\nDo you approve this research plan?", default=True):
                            console.print("[yellow]Plan rejected. You can resume later with 'margre resume'.[/yellow]")
                            return
                        # Update state with approval
                        graph.update_state(config, {"user_approved_plan": True})
                
                # Resume
                current_state = None
                continue

            # 2. Aggregator Interrupt (Review/Refinement)
            if "END" in next_nodes or not next_nodes:
                # Actually if it's interrupted AFTER aggregator, it might be for refinement
                pass
            
            # Check for gaps if we stopped after aggregator
            state_values = graph_state.values
            if state_values.get("master_report"):
                console.print(f"\n[bold green]Master Report Synthesized (Loop {state_values.get('loop_count')}):[/bold green]")
                # Show first 500 chars
                summary = state_values.get("master_report")[:500] + "..."
                console.print(Panel(summary, title="Report Preview", border_style="green"))
                
                gaps = state_values.get("suggested_gaps")
                if gaps:
                    console.print("[bold yellow]Suggested Gaps for Refinement:[/bold yellow]")
                    for gap in gaps:
                        console.print(f" - {gap}")
                    
                    if typer.confirm("\nWould you like to refine the research based on these gaps?", default=False):
                        # Proceeding to refinement
                        current_state = None
                        continue
                
                # If no gaps or user declines, we end
                console.print("[blue]Finishing research. Final results saved to filesystem.[/blue]")
                break
                
    except Exception as e:
        console.print(f"[bold red]Workflow error: {e}[/bold red]")
        import traceback
        logger.debug(traceback.format_exc())
    finally:
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
        
    console.print(Panel(f"[bold cyan]Run Details:[/bold cyan] {run_id}", border_style="blue"))
    console.print(f"[bold green]Query:[/bold green] {meta.get('query')}")
    console.print(f"[bold green]Agents Contributed:[/bold green] {len(meta.get('agents_involved', []))}")
    
    if meta.get("final_report_path"):
        console.print(f"[bold green]Final Report:[/bold green] [underline]{meta.get('final_report_path')}[/underline]")
    
    if meta.get("master_report"):
        summary = meta.get("master_report")[:800] + "..."
        console.print("\n[bold cyan]Report Preview:[/bold cyan]")
        console.print(Panel(summary, border_style="green"))

if __name__ == "__main__":
    app()
