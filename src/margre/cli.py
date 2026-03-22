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
from margre.workflow.orchestrator import app as graph_app

app = typer.Typer(help="MARGRe — Multi-Agent Relation Graph Researcher")
console = Console()

@app.command()
def init():
    """Initialize the application configuration, checking Neo4j connection."""
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
def research(query: str, approve: bool = False):
    """Execute the multi-agent research workflow."""
    console.print(Panel(f"[bold cyan]Researching:[/bold cyan] {query}", border_style="blue"))
    
    # 1. State Initialisation
    initial_state = {
        "query": query,
        "messages": [],
        "plan": None,
        "agent_results": [],
        "current_loop": 1,
        "user_approved_plan": approve
    }
    
    config = {"configurable": {"thread_id": "test_run"}} # Mock thread for local POC
    
    try:
        # We use app.stream to handle the HITL point after the planner
        for step_data in graph_app.stream(initial_state, config):
            for node_name, result in step_data.items():
                if node_name == "planner_node":
                    plan = result.get("plan")
                    if not plan:
                        console.print("[red]Planner failed to generate a plan.[/red]")
                        return
                        
                    # Print the plan for review
                    console.print(f"\n[bold green]Research Plan Generated:[/bold green]")
                    for idx, task in enumerate(plan.subtasks, 1):
                        console.print(f"  {idx}. [cyan]{task.entity_name}[/cyan] ({task.entity_type}): {task.research_query}")
                    
                    # HITL: Ask for approval if not pre-approved
                    if not approve:
                        if not typer.confirm("\nDo you approve this research plan?", default=True):
                            console.print("[yellow]Plan rejected. Exiting.[/yellow]")
                            return
                        # Resume with approval (In a real stateful app, we'd update state and resume)
                        # For now, we continue the stream with the approved flag if it wasn't pre-approved
                        # actually, LangGraph v2 uses interrupts. Let's simplify for Phase 3 deliverable.
                        approve = True
                
                elif node_name == "researcher_node":
                    # results summarize what happened
                    pass
        
        console.print(Panel.fit("[bold green]Research phase completed successfully![/bold green]", border_style="green"))
        
    except Exception as e:
        console.print(f"[bold red]Research workflow failed: {e}[/bold red]")
    finally:
        close_driver()

if __name__ == "__main__":
    app()
