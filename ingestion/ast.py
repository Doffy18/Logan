# import os
# import ast
# from pathlib import Path
# from typing import Dict, List, Any, Set
# import ollama, sqlite3
# from ingestion.database import init_chroma_db, init_sqlite

# class CodeASTVisitor(ast.NodeVisitor):
#     def __init__(self, source_code: str, filepath: str):
#         self.source_lines = source_code.splitlines()
#         self.filepath = filepath
#         self.symbols: List[Dict[str, Any]] = []
#         self.chunks: List[Dict[str, Any]] = []

#     def visit_Import(self, node):
#         for alias in node.names:
#             self.symbols.append({
#                 'name': alias.name, 'type': 'import', 'start_line': node.lineno, 'end_line': node.end_lineno, 'docstring': None
#             })

#     def visit_ImportFrom(self, node: ast.ImportFrom):
#         module = node.module or ""
#         for alias in node.names:
#             self.symbols.append({
#                 "name": f"{module}.{alias.name}", "type": "import", 
#                 "start_line": node.lineno, "end_line": node.end_lineno, "docstring": None
#             })
#         self.generic_visit(node)

#     def visit_FunctionDef(self, node: ast.FunctionDef):
#         self._process_callable(node, "function")
#         self.generic_visit(node)

#     def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
#         self._process_callable(node, "function")
#         self.generic_visit(node)

#     def visit_ClassDef(self, node: ast.ClassDef):
#         docstring = ast.get_docstring(node)
#         code_chunk = "\n".join(self.source_lines[node.lineno - 1 : node.end_lineno])
        
#         self.symbols.append({
#             "name": node.name, "type": "class", 
#             "start_line": node.lineno, "end_line": node.end_lineno, "docstring": docstring
#         })
        
#         self.chunks.append({
#             "id": f"{self.filepath}::class::{node.name}::{node.lineno}",
#             "text": code_chunk,
#             "metadata": {
#                 "filepath": self.filepath, "name": node.name, "type": "class",
#                 "start_line": node.lineno, "end_line": node.end_lineno
#             }
#         })
#         self.generic_visit(node)



#     def _process_callable(self, node, symbol_type: str):
#         docstring = ast.get_docstring(node)
#         code_chunk = "\n".join(self.source_lines[node.lineno - 1 : node.end_lineno])
        
#         self.symbols.append({
#             "name": node.name, "type": symbol_type, 
#             "start_line": node.lineno, "end_line": node.end_lineno, "docstring": docstring
#         })
        
#         self.chunks.append({
#             "id": f"{self.filepath}::{symbol_type}::{node.name}::{node.lineno}",
#             "text": code_chunk,
#             "metadata": {
#                 "filepath": self.filepath, "name": node.name, "type": symbol_type,
#                 "start_line": node.lineno, "end_line": node.end_lineno
#             }
#         })



# def parse_python_file(path: Path):
#     """Safely reads and parses a Python file into symbols and code chunks."""
#     try:
#         with open(path,'r',encoding='utf-8') as f:
#             code = f.read()
#         tree = ast.parse(code,filename=str(path))
#         visitor = CodeASTVisitor(code, filepath= str(path))
#         visitor.visit(tree)
#         return visitor.symbols, visitor.chunks
#     except (SyntaxError, UnicodeDecodeError) as e:
#         print(f" [Parse Error] Failed to parse {path}: {e}")
#         return [], []



# def get_ollama_embedding(text: str, model: str = 'nomic-embed-text') -> List[float]:
#     """Generates vector embeddings via local Ollama instance."""
#     truncated_text = text[:6000]
#     response = ollama.embeddings(model = model, prompt = truncated_text)
#     return response['embedding']




# DEFAULT_IGNORE_DIRS: Set[str] = {
#     ".git", "__pycache__", ".venv", "venv", "env", 
#     ".pytest_cache", ".mypy_cache", "build", "dist", ".egg-info", "chroma_db","logan"
# }
# def scan_directory(root_dir: str, ignore_dirs: Set[str] = DEFAULT_IGNORE_DIRS) -> List[Path]:
#     """Recursively walks through folders to discover all valid Python files."""
#     python_files = []
#     root_path = Path(root_dir).resolve()

#     for root, dirs, files in os.walk(root_path):
#         # Prune ignored directories in-place to stop traversing into them
#         dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
#         for file in files:
#             if file.endswith(".py"):
#                 full_path = Path(root) / file
#                 python_files.append(full_path)

#     return python_files



# def process_codebase(root_dir: str, sqlite_conn: sqlite3.Connection, chroma_collection):
#     """Walks the folder tree, parses files, and updates SQLite and ChromaDB."""
#     target_files = scan_directory(root_dir)
#     print(f" Discovered {len(target_files)} Python files across directories in: {root_dir}\n")

#     for filepath in target_files:
#         str_path = str(filepath)
#         print(f" Processing: {filepath.relative_to(Path(root_dir).resolve())}")
        
#         symbols, chunks = parse_python_file(filepath)
#         if not symbols and not chunks:
#             continue

#         # Update SQLite Metadata
#         cursor = sqlite_conn.cursor()
#         cursor.execute("INSERT OR REPLACE INTO files (filepath) VALUES (?)", (str_path,))
#         cursor.execute("DELETE FROM symbols WHERE filepath = ?", (str_path,))
        
#         for sym in symbols:
#             cursor.execute(
#                 """INSERT INTO symbols (filepath, name, type, start_line, end_line, docstring)
#                    VALUES (?, ?, ?, ?, ?, ?)""",
#                 (str_path, sym["name"], sym["type"], sym["start_line"], sym["end_line"], sym["docstring"])
#             )
#         sqlite_conn.commit()

#         # Generate Embeddings & Upsert to ChromaDB
#         for chunk in chunks:
#             vector = get_ollama_embedding(chunk["text"])
#             chroma_collection.upsert(
#                 ids=[chunk["id"]],
#                 embeddings=[vector],
#                 documents=[chunk["text"]],
#                 metadatas=[chunk["metadata"]]
#             )

#     print(f"\n Finished processing codebase directory!")





import os
import ast
from pathlib import Path
from typing import Dict, List, Any, Set, Optional
import ollama
import sqlite3
from ingestion.database import init_chroma_db, init_sqlite


class CodeASTVisitor(ast.NodeVisitor):
    def __init__(self, source_code: str, filepath: str):
        self.source_lines = source_code.splitlines()
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.symbols: List[Dict[str, Any]] = []
        self.chunks: List[Dict[str, Any]] = []
        self.current_class: Optional[str] = None

    def visit_Import(self, node):
        for alias in node.names:
            self.symbols.append({
                'name': alias.name, 
                'type': 'import', 
                'start_line': node.lineno, 
                'end_line': node.end_lineno, 
                'docstring': None,
                'parent_symbol': None
            })

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            self.symbols.append({
                "name": f"{module}.{alias.name}", 
                "type": "import", 
                "start_line": node.lineno, 
                "end_line": node.end_lineno, 
                "docstring": None,
                "parent_symbol": None
            })
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        docstring = ast.get_docstring(node)
        raw_code = "\n".join(self.source_lines[node.lineno - 1 : node.end_lineno])
        
        # Prepend structured metadata header to chunk text
        header = f"File: {self.filename} ({self.filepath}) | Type: class | Name: {node.name}"
        if docstring:
            header += f"\nDocstring: {docstring}"
        chunk_text = f"{header}\nCode:\n{raw_code}"

        self.symbols.append({
            "name": node.name, 
            "type": "class", 
            "start_line": node.lineno, 
            "end_line": node.end_lineno, 
            "docstring": docstring,
            "parent_symbol": None
        })
        
        self.chunks.append({
            "id": f"{self.filepath}::class::{node.name}::{node.lineno}",
            "text": chunk_text,
            "metadata": {
                "filepath": self.filepath, 
                "filename": self.filename,
                "name": node.name, 
                "type": "class",
                "start_line": node.lineno, 
                "end_line": node.end_lineno
            }
        })
        
        # Track class context for nested methods
        previous_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = previous_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_callable(node, "function")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_callable(node, "function")
        self.generic_visit(node)

    def _process_callable(self, node, symbol_type: str):
        docstring = ast.get_docstring(node)
        raw_code = "\n".join(self.source_lines[node.lineno - 1 : node.end_lineno])
        
        symbol_fullname = f"{self.current_class}.{node.name}" if self.current_class else node.name
        
        # Prepend structured metadata header to chunk text
        header_parts = [
            f"File: {self.filename} ({self.filepath})",
            f"Type: {symbol_type}",
            f"Name: {symbol_fullname}"
        ]
        if self.current_class:
            header_parts.append(f"Class: {self.current_class}")
        
        header = " | ".join(header_parts)
        if docstring:
            header += f"\nDocstring: {docstring}"
            
        chunk_text = f"{header}\nCode:\n{raw_code}"

        self.symbols.append({
            "name": symbol_fullname, 
            "type": symbol_type, 
            "start_line": node.lineno, 
            "end_line": node.end_lineno, 
            "docstring": docstring,
            "parent_symbol": self.current_class
        })
        
        self.chunks.append({
            "id": f"{self.filepath}::{symbol_type}::{symbol_fullname}::{node.lineno}",
            "text": chunk_text,
            "metadata": {
                "filepath": self.filepath, 
                "filename": self.filename,
                "name": symbol_fullname, 
                "type": symbol_type,
                "start_line": node.lineno, 
                "end_line": node.end_lineno
            }
        })


def parse_python_file(path: Path):
    """Safely reads and parses a Python file into symbols and AST code chunks."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        if not code.strip():
            return [], []

        filepath_str = str(path)
        tree = ast.parse(code, filename=filepath_str)
        visitor = CodeASTVisitor(code, filepath=filepath_str)
        visitor.visit(tree)

        # Fallback overview chunk for top-level code or files without functions/classes
        if not visitor.chunks:
            filename = path.name
            header = f"File: {filename} ({filepath_str}) | Type: file_overview"
            chunk_text = f"{header}\nCode:\n{code[:3000]}"
            visitor.chunks.append({
                "id": f"{filepath_str}::file_overview::1",
                "text": chunk_text,
                "metadata": {
                    "filepath": filepath_str,
                    "filename": filename,
                    "name": filename,
                    "type": "file_overview",
                    "start_line": 1,
                    "end_line": len(code.splitlines())
                }
            })

        return visitor.symbols, visitor.chunks
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f" [Parse Error] Failed to parse {path}: {e}")
        return [], []


def get_ollama_embedding(text: str, model: str = 'nomic-embed-text') -> List[float]:
    """Generates vector embeddings via local Ollama instance."""
    truncated_text = text[:6000]
    response = ollama.embeddings(model=model, prompt=truncated_text)
    return response['embedding']


DEFAULT_IGNORE_DIRS: Set[str] = {
    ".git", "__pycache__", ".venv", "venv", "env", 
    ".pytest_cache", ".mypy_cache", "build", "dist", ".egg-info", "chroma_db", "logan"
}

def scan_directory(root_dir: str, ignore_dirs: Set[str] = DEFAULT_IGNORE_DIRS) -> List[Path]:
    """Recursively walks through folders to discover all valid Python files."""
    python_files = []
    root_path = Path(root_dir).resolve()

    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            if file.endswith(".py"):
                full_path = Path(root) / file
                python_files.append(full_path)

    return python_files


def process_codebase(root_dir: str, sqlite_conn: sqlite3.Connection, chroma_collection):
    """Walks the folder tree, parses files, and updates SQLite and ChromaDB."""
    target_files = scan_directory(root_dir)
    print(f" Discovered {len(target_files)} Python files across directories in: {root_dir}\n")

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
                """INSERT INTO symbols (filepath, name, type, start_line, end_line, docstring, parent_symbol)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str_path, sym["name"], sym["type"], sym["start_line"], sym["end_line"], sym["docstring"], sym.get("parent_symbol"))
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