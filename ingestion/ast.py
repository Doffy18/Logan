import os
import ast
from pathlib import Path
from typing import Dict, List, Any, Set
import ollama
from ingestion.database import init_chroma_db, init_sqlite

class CodeASTVisitor(ast.NodeVisitor):
    def __init__(self, source_code: str, filepath: str):
        self.source_lines = source_code.splitlines()
        self.filepath = filepath
        self.symbols: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []

    def visit_Import(self, node):
        for alias in node.names:
            self.symbols.append({
                'name': alias.name, 'type': 'import', 'start_line': node.lineno, 'end_line': node.end_lineno, 'docstring': None
            })

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            self.symbols.append({
                "name": f"{module}.{alias.name}", "type": "import", 
                "start_line": node.lineno, "end_line": node.end_lineno, "docstring": None
            })
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_callable(node, "function")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_callable(node, "function")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        docstring = ast.get_docstring(node)
        code_chunk = "\n".join(self.source_lines[node.lineno - 1 : node.end_lineno])
        
        self.symbols.append({
            "name": node.name, "type": "class", 
            "start_line": node.lineno, "end_line": node.end_lineno, "docstring": docstring
        })
        
        self.chunks.append({
            "id": f"{self.filepath}::class::{node.name}::{node.lineno}",
            "text": code_chunk,
            "metadata": {
                "filepath": self.filepath, "name": node.name, "type": "class",
                "start_line": node.lineno, "end_line": node.end_lineno
            }
        })
        self.generic_visit(node)

    


def _process_callable(self, node, symbol_type: str):
        docstring = ast.get_docstring(node)
        code_chunk = "\n".join(self.source_lines[node.lineno - 1 : node.end_lineno])
        
        self.symbols.append({
            "name": node.name, "type": symbol_type, 
            "start_line": node.lineno, "end_line": node.end_lineno, "docstring": docstring
        })
        
        self.chunks.append({
            "id": f"{self.filepath}::{symbol_type}::{node.name}::{node.lineno}",
            "text": code_chunk,
            "metadata": {
                "filepath": self.filepath, "name": node.name, "type": symbol_type,
                "start_line": node.lineno, "end_line": node.end_lineno
            }
        })



def parse_python_file(path: Path):
    """Safely reads and parses a Python file into symbols and code chunks."""
    try:
        with open(path,'r',encoding='utf-8') as f:
            code = f.read()
        tree = ast.parse(code,filename=str(path))
        visitor = CodeASTVisitor(code, filepath= str(path))
        visitor.visit(tree)
        return visitor.symbols, visitor.chunks
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f" [Parse Error] Failed to parse {path}: {e}")
        return [], []



def get_ollama_embedding(text: str, model: str = 'nomic-embed-text') -> List[float]:
    """Generates vector embeddings via local Ollama instance."""
    response = ollama.embeddings(model = model, prompt = text)
    return response['embedding']




DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git", "__pycache__", ".venv", "venv", "env", 
    ".pytest_cache", ".mypy_cache", "build", "dist", ".egg-info", "chroma_db"
}
def scan_directory(root_dir: str, ignore_dirs: Set[str] = DEFAULT_IGNORE_DIRS) -> List[Path]:
    """Recursively walks through folders to discover all valid Python files."""
    python_files = []
    root_path = Path(root_dir).resolve()

    for root, dirs, files in os.walk(root_path):
        # Prune ignored directories in-place to stop traversing into them
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            if file.endswith(".py"):
                full_path = Path(root) / file
                python_files.append(full_path)

    return python_files



def process_codebase(root_dir: str, sqlite_conn: sqlite3.Connection, chroma_collection):
    """Walks the folder tree, parses files, and updates SQLite and ChromaDB."""
    target_files = scan_directory(root_dir)
    print(f"🔍 Discovered {len(target_files)} Python files across directories in: {root_dir}\n")

    for filepath in target_files:
        str_path = str(filepath)
        print(f" Processing: {filepath.relative_to(Path(root_dir).resolve())}")
        
        symbols, chunks = parse_python_file(filepath)
        if not symbols and not chunks:
            continue

        # Update SQLite Metadata
        cursor = sqlite_conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO files (filepath) VALUES (?)", (str_path,))
        cursor.execute("DELETE FROM symbols WHERE filepath = ?", (str_path,))
        
        for sym in symbols:
            cursor.execute(
                """INSERT INTO symbols (filepath, name, type, start_line, end_line, docstring)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str_path, sym["name"], sym["type"], sym["start_line"], sym["end_line"], sym["docstring"])
            )
        sqlite_conn.commit()

        # Generate Embeddings & Upsert to ChromaDB
        for chunk in chunks:
            vector = get_ollama_embedding(chunk["text"])
            chroma_collection.upsert(
                ids=[chunk["id"]],
                embeddings=[vector],
                documents=[chunk["text"]],
                metadatas=[chunk["metadata"]]
            )

    print(f"\n Finished processing codebase directory!")




if __name__ == "__main__":
    db_conn = init_sqlite()
    vector_coll = init_chroma_db()
    # Pass any project folder path here (e.g., "." for current project directory)
    project_root = "." 
    process_codebase(project_root, db_conn, vector_coll)
    db_conn.close()