import os
import sys

import click
from rich.console import Console
from rich.panel import Panel

from agent import AgentState, build_context_engine_graph

console = Console()

@click.group()
def cli():
    """ContextEngine: LangGraph Agentic Search REPL."""
    pass

@cli.command()
def chat():
    """Start the interactive LangGraph agent REPL session."""
    if not os.environ.get("GEMINI_API_KEY"):
        console.print("[bold red]Error:[/bold red] GEMINI_API_KEY environment variable is missing.")
        sys.exit(1)

    console.print("[dim]Compiling LangGraph StateGraph...[/dim]")
    graph = build_context_engine_graph()

    console.print(Panel(
        "[bold cyan]LangGraph ContextEngine Active[/bold cyan]\n"
        "Ask questions about your codebase. Type [bold yellow]'exit'[/bold yellow] or [bold yellow]'quit'[/bold yellow] to stop.",
        border_style="cyan"
    ))

    while True:
        try:
            user_input = click.prompt(click.style("\nUser", fg="cyan", bold=True))
            if user_input.strip().lower() in ["exit", "quit", "q"]:
                break
            if not user_input.strip():
                continue

            # Instantiate Pydantic state and invoke the graph execution
            initial_state = AgentState(query=user_input)
            graph.invoke(initial_state)

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold yellow]Session terminated.[/bold yellow]")
            break

if __name__ == "__main__":
    cli()