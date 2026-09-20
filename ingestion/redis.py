import redis
import subprocess
import hashlib
from pathlib import Path
from typing import List, Tuple
from ingestion.ast import get_ollama_embedding, parse_python_file, scan_directory, init_chroma_db, init_sqlite


def ensure_redis_container() -> None:
    """Checks if the Redis Docker container is running, starting or creating it automatically."""
    try:
        # Check if container named 'redis-cache' is running
        status = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", "redis-cache"],
            capture_output=True,
            text=True
        ).stdout.strip()

        if status == "true":
            return  # Container is running

        if status == "false":
            print("🚀 Starting existing Redis Docker container...")
            subprocess.run(["docker", "start", "redis-cache"], check=True)
            return

    except Exception:
        pass  # Container doesn't exist yet; proceed to create it

    print("📦 Spinning up new Redis Docker container...")
    subprocess.run(
        ["docker", "run", "-d", "-p", "6379:6379", "--name", "redis-cache", "redis:alpine"],
        check=True
    )


def init_redis() -> redis.Redis:
    """Connects to Redis, auto-starting the container if necessary."""
    try:
        r = redis.Redis(decode_responses=True)
        r.ping()
        print('connected to redis')
        return r
    except redis.ConnectionError:
        ensure_redis_container()
        r = redis.Redis(decode_responses=True)
        r.ping()
        print('connected to redis')
        return r


def calculate_sha256(filepath: Path) -> str:
    """Computes a SHA-256 hash of a file's raw content."""
    with open(filepath, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def is_file_changed(filepath: Path, redis_client: redis.Redis) -> Tuple[bool, str]:
    """
    Checks if a file's SHA-256 hash matches the value in Redis.
    Returns (True, current_hash) if modified/new, else (False, current_hash).
    """
    current_hash = calculate_sha256(filepath)
    redis_key = f"codebase:hash:{filepath.resolve()}"
    cached_hash = redis_client.get(redis_key)
    if cached_hash == current_hash:
        return False, current_hash
    return True, current_hash


def update_redis_hash(filepath: Path, file_hash: str, redis_client: redis.Redis) -> None:
    """Saves the latest file SHA-256 hash into Redis."""
    redis_key = f"codebase:hash:{filepath.resolve()}"
    redis_client.set(redis_key, file_hash)


def process_single_file(filepath: Path, sqlite_conn, chroma_collection) -> None:
    """Processes AST parsing and vector upsert for a single modified file."""
    str_path = str(filepath)
    symbols, chunks = parse_python_file(filepath)

    if not symbols and not chunks:
        return

    # Writing AST metadata to SQLite
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

    # Batch vector embeddings into ChromaDB
    for chunk in chunks:
        vector = get_ollama_embedding(chunk["text"])
        chroma_collection.upsert(
            ids=[chunk["id"]],
            embeddings=[vector],
            documents=[chunk["text"]],
            metadatas=[chunk["metadata"]]
        )


def process_codebase_with_cache(root_dir: str, redis_client: redis.Redis, sqlite_conn, chroma_collection) -> None:
    """Scans directory and uses Redis delta caching to skip unchanged files."""
    root_path = Path(root_dir).resolve()
    target_files = scan_directory(root_dir)

    processed_count = 0
    skipped_count = 0

    for filepath in target_files:
        rel_path = filepath.relative_to(root_path)
        changed, current_hash = is_file_changed(filepath, redis_client)

        if not changed:
            print(f"⏩ [SKIPPED] {rel_path} (Hash Unchanged)")
            skipped_count += 1
            continue
        print(f"🔄 [PROCESSING] {rel_path} (Modified/New)")

        process_single_file(filepath, sqlite_conn, chroma_collection)  # ast parsing and embedding
        update_redis_hash(filepath, current_hash, redis_client)  # cache hash after successful processing
        processed_count += 1
    print("-" * 50)
    print(f"Summary: {processed_count} processed, {skipped_count} skipped (cached).\n")


if __name__ == "__main__":
    redis_client = init_redis()
    db_conn = init_sqlite()
    vector_coll = init_chroma_db()

    project_root = "."
    print("\n--- FIRST PASS ---")
    process_codebase_with_cache(project_root, redis_client, db_conn, vector_coll)
    print("\n--- SECOND PASS (Testing Cache Hits) ---")
    process_codebase_with_cache(project_root, redis_client, db_conn, vector_coll)
    db_conn.close()