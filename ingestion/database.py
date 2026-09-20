import chromadb
import ollama
import sqlite3

def init_sqlite(db_path: str = 'codebase_metadata.db') -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Table for tracking processed files
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT UNIQUE NOT NULL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Table for structural symbols (Functions, Classes, Imports)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL, -- 'function', 'class', 'import'
            start_line INTEGER,
            end_line INTEGER,
            docstring TEXT,
            parent_symbol TEXT,
            FOREIGN KEY (filepath) REFERENCES files (filepath)
        )
    """)
    conn.commit()
    return conn

def init_chroma_db(persist_directory: str = "./chroma_db"):
    """Initializes persistent ChromaDB client and collection."""
    chroma_client = chromadb.PersistentClient(path=persist_directory)
    collection = chroma_client.get_or_create_collection(
        name="codebase_embeddings",
        metadata={"hnsw:space": "cosine"}
    )
    return collection