"""CLI entry point for MARGRe."""

import os
import shutil
import typer
from rich.console import Console
from rich.panel import Panel

from margre.config import load_config
from margre.graph.connection import verify_connection, close_driver
from margre.graph.schema import init_schema

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

if __name__ == "__main__":
    app()
