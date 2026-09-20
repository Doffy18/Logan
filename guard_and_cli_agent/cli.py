
import os
import sys
import json
import asyncio
from pathlib import Path

# Add project root to sys.path so internal imports resolve anywhere
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Add package directory to sys.path as fallback
PACKAGE_DIR = Path(__file__).resolve().parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

import typer
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from langchain_core.messages import HumanMessage

# Internal package imports
try:
    from guard_and_cli_agent.agent import AgentState, build_context_engine_graph
except ModuleNotFoundError:
    from agent import AgentState, build_context_engine_graph

# Import Watchdog non-blocking background observer
try:
    from ingestion.monitoring import start_observer_background
except ModuleNotFoundError:
    start_observer_background = None

app = typer.Typer(help="Logan AI Interactive Assistant CLI.")
console = Console()

# Hidden configuration storage path in the user's home directory
CONFIG_FILE = Path.home() / ".logan_config.json"


def load_config() -> dict:
    """Reads cached configuration if it exists."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(gemini_key: str, langsmith_key: str = "", langsmith_project: str = "logan-agent", root_dir: str = "."):
    """Caches configurations to a local hidden JSON file."""
    config_data = {
        "GEMINI_API_KEY": gemini_key,
        "LANGSMITH_API_KEY": langsmith_key,
        "LANGSMITH_PROJECT": langsmith_project,
        "LOGAN_WORKSPACE_ROOT": root_dir,
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        console.print(f"[yellow]⚠️ Warning: Could not cache configuration file locally: {e}[/yellow]")


def run_interactive_prompts(cached_config: dict) -> tuple:
    """Prompts the user for configuration keys sequentially."""
    console.print("\n[bold yellow]⚙️ Please update or verify your Logan AI configurations:[/bold yellow]")
    default_project = cached_config.get("LANGSMITH_PROJECT", "logan-agent")
    default_gemini = cached_config.get("GEMINI_API_KEY", "")
    default_ls_key = cached_config.get("LANGSMITH_API_KEY", "")

    gemini_key = typer.prompt("🔑 Enter your Gemini API Key", default=default_gemini, hide_input=True, show_default=False)
    langsmith_key = typer.prompt("🔑 Enter your LangSmith API Key (Press Enter to skip)", default=default_ls_key, hide_input=True, show_default=False)
    langsmith_project = typer.prompt("📌 Enter LangSmith Project Name", default=default_project) if langsmith_key else ""
    
    root_dir = str(Path.cwd().resolve())
    return gemini_key, langsmith_key, langsmith_project, root_dir


def apply_environment_vars(gemini_key: str, langsmith_key: str, langsmith_project: str, root_dir: str):
    """Sets variables into os.environ for current process runtime."""
    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key
        os.environ["GOOGLE_API_KEY"] = gemini_key  # Required for LangChain Google integrations
    
    if langsmith_key.strip():
        os.environ["LANGSMITH_API_KEY"] = langsmith_key
        os.environ["LANGCHAIN_API_KEY"] = langsmith_key
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
    if langsmith_project.strip():
        os.environ["LANGSMITH_PROJECT"] = langsmith_project
        os.environ["LANGCHAIN_PROJECT"] = langsmith_project

    os.environ["LOGAN_WORKSPACE_ROOT"] = root_dir


@app.callback(invoke_without_command=True)
def main():
    """Launches the primary interactive session loop for Logan AI directly."""
    console.print(Panel("[bold cyan]🤖 Logan AI Workspace Configuration Initialization[/bold cyan]", border_style="cyan"))

    cached_config = load_config()

    gemini_key = cached_config.get("GEMINI_API_KEY")
    langsmith_key = cached_config.get("LANGSMITH_API_KEY", "")
    langsmith_project = cached_config.get("LANGSMITH_PROJECT", "logan-agent")
    root_dir = str(Path.cwd().resolve())

    if not gemini_key:
        gemini_key, langsmith_key, langsmith_project, root_dir = run_interactive_prompts(cached_config)

    apply_environment_vars(gemini_key, langsmith_key, langsmith_project, root_dir)
    save_config(gemini_key, langsmith_key, langsmith_project, root_dir)

    console.print(f"\n[bold green]✔ Environment Context verified! Active Workspace: [white]{root_dir}[/white][/bold green]")

    # Start Real-Time Watchdog File Observer in Non-Blocking Background Thread
    if start_observer_background:
        start_observer_background(root_dir)

    console.print(Panel(
        "[bold magenta]🤖 Welcome to your Logan AI Interactive Session Space.[/bold magenta]\n"
        "Ask questions or run automated workspace tasks directly.\n\n"
        "[bold yellow]Configuration Shortcuts Available Anywhere:[/bold yellow]\n"
        "  • [cyan]:config[/cyan]          -> Reset API settings sequentially\n"
        "  • [cyan]:config:gemini[/cyan]   -> Update Gemini API Key only\n"
        "  • [cyan]:config:smith[/cyan]    -> Update LangSmith Keys/Project only\n"
        "  • [cyan]exit[/cyan] / [cyan]quit[/cyan]      -> Close out session cleanly",
        border_style="magenta"
    ))

    # Compile Graph Workflow
    graph = build_context_engine_graph()

    # Session thread ID for conversation continuity
    session_config = {"configurable": {"thread_id": "logan_interactive_session"}}

    while True:
        try:
            user_input = console.input("[bold cyan]logan ❯ [/bold cyan]").strip()

            if user_input.lower() in ["exit", "quit"]:
                console.print("[bold red]Exiting session. Goodbye![/bold red]\n")
                break

            if not user_input:
                continue

            if user_input.lower().startswith(":config"):
                cmd = user_input.lower()
                cached_config = load_config()

                if cmd == ":config:gemini":
                    gemini_key = typer.prompt("🔑 Enter your Gemini API Key", hide_input=True, show_default=False)
                    apply_environment_vars(gemini_key, langsmith_key, langsmith_project, root_dir)
                    console.print("[bold green]✔ Gemini API Key updated![/bold green]\n")

                elif cmd == ":config:smith":
                    langsmith_key = typer.prompt("🔑 Enter your LangSmith API Key (Press Enter to disable)", default="", hide_input=True, show_default=False)
                    if langsmith_key:
                        langsmith_project = typer.prompt("📌 Enter LangSmith Project Name", default="logan-agent")
                    else:
                        langsmith_project = ""
                        os.environ.pop("LANGSMITH_TRACING", None)
                        os.environ.pop("LANGCHAIN_TRACING_V2", None)
                    apply_environment_vars(gemini_key, langsmith_key, langsmith_project, root_dir)
                    console.print("[bold green]✔ LangSmith configuration updated![/bold green]\n")

                elif cmd == ":config":
                    gemini_key, langsmith_key, langsmith_project, root_dir = run_interactive_prompts(cached_config)
                    apply_environment_vars(gemini_key, langsmith_key, langsmith_project, root_dir)
                    console.print("[bold green]✔ Full context configuration updated successfully![/bold green]\n")

                else:
                    console.print("[bold red]❌ Unknown option. Use :config, :config:gemini, or :config:smith[/bold red]\n")
                    continue

                save_config(gemini_key, langsmith_key, langsmith_project, root_dir)
                continue

            # Initial State Payload
            initial_state = {
                "query": user_input,
                "messages": [HumanMessage(content=user_input)],
            }

            # Invoke graph directly without enclosing in Status spinner to allow LLM token streaming
            graph.invoke(initial_state, config=session_config)

        except KeyboardInterrupt:
            console.print("\n[bold red]Session closed cleanly.[/bold red]\n")
            break
        except Exception as e:
            def print_exception_deeply(err, depth=1):
                if hasattr(err, "exceptions") and err.exceptions:
                    for sub_err in err.exceptions:
                        print_exception_deeply(sub_err, depth + 1)
                else:
                    console.print(f"{'  ' * depth}[bold red]💥 Root Cause Exception:[/bold red] [yellow]{type(err).__name__}[/yellow]: {err}")

            console.print("[bold red]System Runtime Exception error triggered:[/bold red]")
            print_exception_deeply(e)
            console.print("")


if __name__ == "__main__":
    app()