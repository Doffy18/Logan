import os
import re
from pathlib import Path
from typing import List, Dict, Any
from pydantic import BaseModel, Field

# LangChain & LangGraph Imports
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, START, END

from ingestion.database import init_sqlite, init_chroma_db
from guard import validate_prompt_security
from ingestion.ast import get_ollama_embedding

from rich.console import Console
from rich.panel import Panel

console = Console()


class AgentState(BaseModel):
    """Encapsulates the state of our agentic execution pipeline using Pydantic."""
    query: str
    is_safe: bool = True
    security_reason: str = ""
    context: str = ""
    messages: List[BaseMessage] = Field(default_factory=list)


def retrieve_context_from_dbs(query: str, db_path: str = "codebase_metadata.db") -> str:
    """Fetches vector chunks from ChromaDB, AST symbols from SQLite, verbatim strings, and raw file contents."""
    sqlite_conn = init_sqlite(db_path)
    chroma_collection = init_chroma_db()
    context_blocks = []

    # Get active workspace directory set by CLI
    workspace_root = os.getenv("LOGAN_WORKSPACE_ROOT", os.getcwd())

    # DIRECT FILE LOOKUP CHECK: Did the user ask for a specific file (e.g. test.py)?
    file_matches = re.findall(r'[\w\-\/\\]+\.(?:py|json|md|txt|yaml|toml|sql)', query, re.IGNORECASE)
    if file_matches:
        context_blocks.append("--- DIRECT FILE READ (Workspace Filesystem) ---")
        for file_name in set(file_matches):
            matched_path = None
            for root, _, files in os.walk(workspace_root):
                if file_name in files or any(f.endswith(file_name) for f in files):
                    matched_path = Path(root) / file_name
                    break

            if matched_path and matched_path.is_file():
                try:
                    with open(matched_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                    context_blocks.append(f"File: {matched_path}\n```python\n{file_content}\n```")
                except Exception as e:
                    context_blocks.append(f"File: {matched_path} (Error reading file: {e})")
            else:
                context_blocks.append(f"File '{file_name}' requested but not found on disk under {workspace_root}.")

    # EXACT QUOTED STRING SEARCH (Lookup strings directly)
    quoted_strings = re.findall(r"['\"](.*?)['\"]", query)
    if quoted_strings:
        exact_matches = []
        for search_term in quoted_strings:
            if len(search_term.strip()) > 1:
                for root, _, files in os.walk(workspace_root):
                    # Skip hidden folders like .venv or .git
                    if any(part.startswith(".") for part in Path(root).parts if part != "."):
                        continue
                    for file in files:
                        if file.endswith((".py", ".json", ".md", ".txt", ".yaml", ".toml")):
                            fpath = Path(root) / file
                            try:
                                with open(fpath, "r", encoding="utf-8") as f:
                                    content = f.read()
                                    if search_term.lower() in content.lower():
                                        exact_matches.append(f"Exact match for '{search_term}' found in {fpath}:\n```python\n{content}\n```")
                            except Exception:
                                pass
        if exact_matches:
            context_blocks.append("--- EXACT STRING SEARCH MATCHES ---")
            context_blocks.extend(exact_matches)

    # 3. ChromaDB Vector Search (Semantic Fallback)
    try:
        emb_res = get_ollama_embedding(query)
        results = chroma_collection.query(
            query_embeddings=[emb_res],
            n_results=3
        )
        if results and results.get("documents") and results["documents"][0]:
            context_blocks.append("--- VECTOR CODE CHUNKS (ChromaDB) ---")
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                filepath = meta.get("filepath", "Unknown File")
                context_blocks.append(f"File: {filepath}\n```python\n{doc}\n```")
    except Exception as e:
        context_blocks.append(f"[Vector Search Error: {str(e)}]")

    # 4. AST Symbol Search in SQLite
    try:
        cursor = sqlite_conn.cursor()
        keywords = [f"%{w}%" for w in query.split() if len(w) > 3]
        if keywords:
            cursor.execute(
                "SELECT filepath, type, name, start_line, end_line FROM symbols WHERE name LIKE ? LIMIT 5",
                (keywords[0],)
            )
            rows = cursor.fetchall()
            if rows:
                context_blocks.append("\n--- AST MATCHED SYMBOLS (SQLite) ---")
                for r in rows:
                    context_blocks.append(f"• {r[1].capitalize()} '{r[2]}' in {r[0]} (Lines {r[3]}-{r[4]})")
    except Exception as e:
        context_blocks.append(f"[SQLite Search Error: {str(e)}]")

    sqlite_conn.close()
    return "\n\n".join(context_blocks) if context_blocks else "No relevant codebase context found."


def security_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Scans user query through path-traversal RegEx & LlamaGuard."""
    console.print("[dim]🔒 Node: security_node (Running LlamaGuard)...[/dim]")
    is_safe, reason = validate_prompt_security(state.query)
    return {"is_safe": is_safe, "security_reason": reason}


def retriever_node(state: AgentState) -> Dict[str, Any]:
    """Node 2: Fetches local AST & vector context if the prompt is safe."""
    console.print("[dim]🔍 Node: retriever_node (Querying ChromaDB & SQLite)...[/dim]")
    context_str = retrieve_context_from_dbs(state.query)
    return {"context": context_str}


def generator_node(state: AgentState) -> Dict[str, Any]:
    """Node 3: Generates response using LangChain init_chat_model."""
    console.print("[dim]⚡ Node: generator_node (Invoking Gemini via init_chat_model)...[/dim]")

    active_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    
    if not active_api_key:
        raise ValueError("Gemini API key missing. Please set GOOGLE_API_KEY or GEMINI_API_KEY in environment.")

    model = init_chat_model(
        model='gemini-2.5-flash',
        model_provider='google_genai',
        api_key=active_api_key
    )
    
    system_message = SystemMessage(content=(
        "You are ContextEngine, an AI codebase assistant running inside a terminal.\n"
        "Answer the user query strictly based on the provided local codebase context.\n"
        f"LOCAL CONTEXT:\n{state.context}"
    ))
    user_msg = HumanMessage(content=state.query)
    console.print("\n[bold green]ContextEngine[/bold green]:")
    
    full_text = ""
    for chunk in model.stream([system_message, user_msg]):
        print(chunk.content, end="", flush=True)
        full_text += chunk.content
    print("\n")
    
    return {"messages": [HumanMessage(content=state.query), AIMessage(content=full_text)]}


def block_node(state: AgentState) -> Dict[str, Any]:
    """Node 4: Terminal node executed if security checks fail."""
    console.print(Panel(
        f"[bold red]Blocked by Security Layer[/bold red]\n{state.security_reason}",
        title="[bold red]Security Guardrail[/bold red]",
        border_style="red"
    ))
    return {}


def check_safety_edge(state: AgentState) -> str:
    """Evaluates the security state and routes to retriever or block node."""
    if state.is_safe:
        return "retriever_node"
    return "block_node"


def build_context_engine_graph():
    """Constructs and returns the compiled LangGraph workflow."""
    builder = StateGraph(AgentState)

    builder.add_node('security_node', security_node)
    builder.add_node('block_node', block_node)
    builder.add_node('generator_node', generator_node)
    builder.add_node('retriever_node', retriever_node)

    builder.add_edge(START, 'security_node')
    builder.add_conditional_edges('security_node', check_safety_edge, {
        'retriever_node': 'retriever_node',
        'block_node': 'block_node'
    })

    builder.add_edge('retriever_node', 'generator_node')
    builder.add_edge('generator_node', END)
    builder.add_edge('block_node', END)

    return builder.compile()