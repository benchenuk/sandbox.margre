"""Health and readiness checks for MARGRe core dependencies."""

import logging
from rich.console import Console
from rich.panel import Panel
from rich.status import Status

from margre.llm.client import get_model
from margre.graph.connection import verify_connection

logger = logging.getLogger(__name__)
console = Console()

def check_readiness(check_llm: bool = True, check_db: bool = True) -> bool:
    """
    Verify shared dependencies are available before execution.
    Returns True if all requested checks pass.
    """
    all_pass = True
    
    with Status("[bold blue]Checking MARGRe readiness...", console=console) as status:
        # 1. Database Check
        if check_db:
            status.update("[blue]Pinging Neo4j Database...")
            if verify_connection():
                logger.info("HEALTH: Neo4j connection verified.")
            else:
                logger.error("HEALTH: Neo4j connection failed!")
                console.print("[bold red]ERROR:[/bold red] Neo4j is not reachable. Check if container is running.")
                all_pass = False
        
        # 2. LLM Check
        if check_llm:
            status.update("[blue]Pinging LLM Provider...")
            try:
                model = get_model()
                # A minimal ping to check API availability
                # We use a very low token limit to minimize latency/cost
                model.invoke("ping") 
                logger.info("HEALTH: LLM provider responded to ping.")
            except Exception as e:
                logger.error(f"HEALTH: LLM connection failed: {e}")
                console.print(f"[bold red]ERROR:[/bold red] LLM provider at '{model.openai_api_base}' is unreachable or returned error: {e}")
                all_pass = False
                
    if not all_pass:
        console.print(Panel(
            "[bold red]Readiness check failed![/bold red]\nPlease ensure all dependencies are running and configured correctly in config.toml.",
            border_style="red"
        ))
        
    return all_pass
