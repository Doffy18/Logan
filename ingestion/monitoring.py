import time
import threading
from pathlib import Path
from typing import Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ingestion.database import (
    init_sqlite,
    init_chroma_db,
    DEFAULT_IGNORE_DIRS,
)
from ingestion.redis import (
    init_redis,
    is_file_changed,
    process_single_file,
    update_redis_hash,
)

class CodeBaseFileHandler(FileSystemEventHandler):
    """
    Listens for OS file save/create events and runs modified Python files
    through the Phase 2 Redis delta-caching pipeline.
    """
    def __init__(self, root_dir: Path, redis_client, sqlite_conn, chroma_collection, ignore_dirs: Set[str] = DEFAULT_IGNORE_DIRS):
        super().__init__()
        self.root_dir = root_dir.resolve()
        self.redis_client = redis_client
        self.sqlite_conn = sqlite_conn
        self.chroma_collection = chroma_collection
        self.ignore_dirs = ignore_dirs

    def _should_ignore_path(self, filepath: Path) -> bool:
        """Helper to check if a path falls inside ignored directories."""
        parts = filepath.parts
        return any(ignored in parts for ignored in self.ignore_dirs)

    def _handle_event(self, event):
        if event.is_directory:
            return
        filepath = Path(event.src_path).resolve()
        if filepath.suffix != ".py" or self._should_ignore_path(filepath):
            return
        
        try:
            rel_path = filepath.relative_to(self.root_dir)
            changed, current_hash = is_file_changed(filepath, self.redis_client)
            if not changed:
                return
            
            print(f"\n⚡ [REAL-TIME EVENT] File Saved: {rel_path}")
            print(f"🔄 Re-indexing AST & Vector DB...")

            process_single_file(filepath, self.sqlite_conn, self.chroma_collection)
            update_redis_hash(filepath, current_hash, self.redis_client)
            print(f"✔ Indexing complete for {rel_path}\n")
        except Exception as e:
            print(f"⚠️ [Watcher Error]: {e}")

    def on_modified(self, event):
        return self._handle_event(event)

    def on_created(self, event):
        return self._handle_event(event)


def start_observer_background(root_dir: str):
    """Spawns Watchdog Observer in a non-blocking background daemon thread."""
    try:
        redis_client = init_redis()
        sqlite_conn = init_sqlite("codebase_metadata.db")
        chroma_collection = init_chroma_db()
        root_path = Path(root_dir).resolve()

        event_handler = CodeBaseFileHandler(
            root_dir=root_path,
            redis_client=redis_client,
            sqlite_conn=sqlite_conn,
            chroma_collection=chroma_collection
        )
        observer = Observer()
        observer.schedule(event_handler, path=str(root_path), recursive=True)
        
        # Start observer in background daemon thread
        thread = threading.Thread(target=observer.start, daemon=True)
        thread.start()
        print(f"[bold green]👀 Real-time Watchdog Observer active on {root_path}[/bold green]")
        return observer
    except Exception as e:
        print(f"[yellow]⚠️ Could not launch Watchdog background watcher: {e}[/yellow]")
        return None





# if __name__ == "__main__":
#     redis_client = init_redis()
#     db_conn = init_sqlite_db()
#     vector_coll = init_chroma_db()
#     target_directory = "."
#     # Start continuous background monitoring
#     start_observer(target_directory, redis_client, db_conn, vector_coll)
#     db_conn.close()