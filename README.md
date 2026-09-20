# ⚡ Local Codebase Context Engine & CLI Agent (`logan`)

 > **Version 1.0.0** | *A $0-Budget, Local-First Codebase Search & RAG Tool for your Terminal* | **Functional Prototype**


The **Local Codebase Context Engine** is a local-first developer tool and CLI agent designed to provide low-latency **codebase search, security filtering, and context retrieval** directly in the terminal.

The CLI command is **`logan`**.

Instead of repeatedly uploading an entire repository to cloud-based AI tools or relying on expensive AI editor subscriptions, `logan` continuously indexes the local codebase and retrieves only the relevant code needed to answer a developer's question.
The system combines **real-time file monitoring, SHA-256 delta caching, AST-based parsing, SQLite metadata indexing, ChromaDB vector search, local Ollama models, LlamaGuard security filtering, and LangGraph orchestration**.

For final reasoning, `logan` uses **Gemini Flash through Google AI Studio's free tier**, sending only the relevant retrieved code context rather than the entire codebase.

---

# ✨ Key Features

* 🔍 **Local Codebase Search** — Search and retrieve relevant code from a local Python codebase.
* 🌲 **AST-Aware Indexing** — Parses Python files into meaningful functions, classes, and methods instead of arbitrary text chunks.
* ⚡ **Real-Time File Watching** — Uses `watchdog` to automatically detect file creation and modification.
* 🔐 **SHA-256 Delta Caching** — Uses Redis to detect unchanged files and avoid unnecessary re-processing.
* 🧠 **Local Embeddings** — Uses Ollama's `nomic-embed-text` model to generate embeddings locally.
* 🗃️ **Hybrid Retrieval** — Combines SQLite structural metadata with ChromaDB semantic vector search.
* 🛡️ **Local Security Filtering** — Uses `llama-guard3:1b` through Ollama to inspect prompts before filesystem and database lookups.
* 🔄 **LangGraph Orchestration** — Coordinates the stateful ingestion and processing workflow.
* 🤖 **Gemini Flash Reasoning** — Uses Google AI Studio for final reasoning over small, retrieved context snippets.
* 💻 **Interactive CLI** — Provides a terminal REPL through the `logan` command.
* 📊 **Observability & Benchmarking** — Supports LangSmith Tracing
* 💰 **$0-Budget Architecture** — Uses local open-source infrastructure and free-tier cloud reasoning.

---

# 🏗️ Architecture & Workflow

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                         DEVELOPER TERMINAL                              │
│                                                                         │
│                              $ logan                                    │
│                                                                         │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    BACKGROUND FILE OBSERVER                             │
│                              watchdog                                   │
│                                                                         │
│       Detect file create / modify / save events in real time            │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         SHA-256 HASHING                                 │
│                                                                         │
│                    Calculate current file hash                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              REDIS                                      │
│                                                                         │
│                    Compare stored file hash                             │
│                                                                         │
│             ┌────────────────────┴────────────────────┐                 │
│             │                                         │                 │
│        HASH MATCH                              HASH CHANGED              │
│             │                                         │                 │
│             ▼                                         ▼                 │
│           SKIP                                  AST PARSING              │
│        PROCESSING                                     │                 │
│                                                     │                   │
│                                            ┌────────┴────────┐          │
│                                            ▼                 ▼          │
│                                         SQLite           ChromaDB       │
│                                       Metadata          Embeddings      │
│                                                               ▲         │
│                                                               │         │
│                                                   Ollama                 │
│                                                nomic-embed-text          │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       LOCAL SECURITY LAYER                              │
│                                                                         │
│                         User Prompt                                     │
│                              │                                          │
│                              ▼                                          │
│                     LlamaGuard via Ollama                               │
│                              │                                          │
│                     ┌────────┴────────┐                                 │
│                     │                 │                                 │
│                   SAFE             UNSAFE                               │
│                     │                 │                                 │
│                     ▼                 ▼                                 │
│                 Retrieval        Block + Log                            │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         LOCAL RETRIEVAL                                 │
│                                                                         │
│                    ┌────────────┴────────────┐                          │
│                    ▼                         ▼                          │
│                 SQLite                   ChromaDB                       │
│              AST Metadata            Semantic Search                   │
│                    │                         │                          │
│                    └────────────┬────────────┘                          │
│                                 │                                       │
│                                 ▼                                       │
│                       Relevant Code Snippets                            │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        REASONING ENGINE                                 │
│                                                                         │
│                    Gemini Flash / Google AI Studio                      │
│                                                                         │
│              User Prompt + Retrieved Local Context                     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
                         Developer Response
```

---

# 🎯 Why `logan`?

The problem this project addresses is simple:

> **How can a developer give an LLM useful context about a large local codebase without repeatedly sending the entire repository to a cloud model?**

`logan` approaches this as an **infrastructure and retrieval problem**, rather than simply maintaining static project notes.

Instead of loading an entire repository into an LLM context window, the system continuously builds a searchable local representation of the codebase.

```text
                 LOCAL CODEBASE
                       │
                       ▼
                Watchdog Observer
                       │
                       ▼
                 SHA-256 Hash
                       │
                       ▼
                    Redis
                       │
              Only process changes
                       │
                       ▼
                AST + Embeddings
                       │
              ┌────────┴────────┐
              ▼                 ▼
           SQLite           ChromaDB
              │                 │
              └────────┬────────┘
                       │
                       ▼
                 Relevant Code
                       │
                       ▼
                 Gemini Flash
```

This means the reasoning model receives **retrieved context**, rather than the entire repository.

---

# 🆚 `logan` vs Static Context Files

Files such as `CLAUDE.md` are useful for storing project-level instructions, conventions, and developer notes.

However, a static markdown file is not a dynamic code search index.

`logan` focuses on a different problem:

| Static Project Notes                | `logan`                                            |
| :---------------------------------- | :------------------------------------------------- |
| Stores developer-written context    | Builds a searchable representation of the codebase |
| Primarily static                    | Automatically updated                              |
| Does not parse the repository       | AST-aware indexing                                 |
| No semantic vector search           | ChromaDB semantic retrieval                        |
| No change detection                 | SHA-256 + Redis delta caching                      |
| No real-time indexing               | Watchdog file observer                             |
| No dedicated local security layer   | Local LlamaGuard filtering                         |
| Context must be manually maintained | Context generated from source code                 |

`logan` and static context files can therefore serve different purposes rather than being direct replacements for one another.

---

# 🔄 Core Data Flow

## 1. File Monitoring

`watchdog` monitors the project directory for filesystem events.

```text
Developer saves file
       │
       ▼
   watchdog
       │
       ▼
SHA-256 calculation
```

This allows the index to stay synchronized with the codebase without requiring the developer to manually trigger indexing.

---

## 2. Redis Delta Caching

Each file's SHA-256 hash is stored in Redis.

Example key:

```text
codebase:hash:<filepath>
```

The current hash is compared with the stored hash.

### Unchanged file

```text
Current Hash == Redis Hash
          │
          ▼
     Skip indexing
```

### Changed file

```text
Current Hash != Redis Hash
          │
          ▼
      Re-index file
```

This prevents unchanged files from being repeatedly parsed and embedded.

---

# 🌲 AST-Based Code Indexing

Changed Python files are parsed using Python's built-in `ast` module.

Rather than splitting code into arbitrary line-based chunks, `logan` identifies meaningful program structures:

```text
Python File
│
├── Class
│   ├── Method
│   ├── Method
│   └── Method
│
├── Function
├── Function
└── Function
```

This produces retrieval units that correspond to actual code definitions.

---

# 🗃️ SQLite Metadata Index

SQLite stores structured information extracted from the AST.

Examples include:

* File paths
* Function definitions
* Class definitions
* Methods
* Symbol names
* Source locations
* Import relationships
* AST metadata

SQLite provides precise structural lookup capabilities that complement semantic vector search.

---

# 🧠 Local Embeddings with Ollama

Code chunks are embedded locally using:

```text
Ollama
└── nomic-embed-text
```

The embeddings are stored in ChromaDB.

This allows semantic queries such as:

```text
"Where is user authentication handled?"
```

to retrieve relevant code even when the exact phrase does not appear in the source.

The embedding stage does **not require a cloud embedding API**.

---

# 🔎 Hybrid Retrieval

`logan` combines structured metadata retrieval with semantic vector retrieval.

```text
                         User Query
                             │
                  ┌──────────┴──────────┐
                  │                     │
                  ▼                     ▼
               SQLite                ChromaDB
            Exact/Structural        Semantic
                Lookup               Search
                  │                     │
                  └──────────┬──────────┘
                             │
                             ▼
                    Retrieved Context
```

### SQLite is useful for:

* Finding a specific function
* Finding a class definition
* Resolving file locations
* Looking up imports
* Resolving known symbols

### ChromaDB is useful for:

* Semantic questions
* Conceptual code searches
* Finding related implementations
* Retrieving code based on meaning

---

# 🛡️ Local Security Layer

Before a user prompt triggers codebase retrieval, it passes through a local security layer.

The project uses **LlamaGuard through Ollama**, specifically the `llama-guard3:1b` model.

```text
User Prompt
     │
     ▼
LlamaGuard
     │
 ┌───┴────┐
 │        │
SAFE    UNSAFE
 │        │
 ▼        ▼
Query   Block
Index   + Log
```

The security layer is designed to help detect and prevent requests involving:

* Prompt injection
* Malicious instructions
* Path traversal
* Unauthorized filesystem access
* Attempts to access sensitive files

The security classification happens locally before the retrieval pipeline proceeds.

---

# 🔄 LangGraph Orchestration

LangGraph coordinates the stateful processing pipeline.

A simplified ingestion workflow:

```text
File Event
    │
    ▼
Hash Check
    │
    ├── Unchanged ──► END
    │
    └── Changed
          │
          ▼
       AST Parse
          │
     ┌────┴────┐
     ▼         ▼
  SQLite    Embedding
               │
               ▼
            ChromaDB
```

A simplified query workflow:

```text
User Prompt
    │
    ▼
Security Check
    │
    ├── Unsafe ──► Block + Log
    │
    └── Safe
         │
         ▼
      Retrieval
         │
    ┌────┴────┐
    ▼         ▼
 SQLite    ChromaDB
    │         │
    └────┬────┘
         │
         ▼
   Context Assembly
         │
         ▼
    Gemini Flash
         │
         ▼
      Response
```

---

# 🤖 Gemini Flash Reasoning

After local security filtering and retrieval, the relevant code context is passed to Gemini Flash through Google AI Studio.

The intended architecture is:

```text
Entire Codebase
      │
      │  remains local
      ▼
Local Index
      │
      ▼
Relevant Code Snippets
      │
      ▼
Gemini Flash
      │
      ▼
Grounded Answer
```

The goal is to avoid sending the entire repository to the reasoning model when only a small portion is relevant to the question.

---

# 💻 CLI Interface

The main interface is the `logan` CLI.

Start an interactive session with:

```bash
logan
```

Example:

```text
$ logan

logan ❯ where is authentication handled?

logan ❯ explain the security_node in agent.py

logan ❯ how does the application connect to Redis?

logan ❯ where are Python files indexed?
```

Rich can be used to provide formatted terminal output, progress indicators, and execution status.

---

# 🧩 Technology Stack

| Layer             | Technology                  | Purpose                         | Execution        |
| :---------------- | :-------------------------- | :------------------------------ | :--------------- |
| **CLI**           | Python + Click/Rich         | Terminal REPL and interface     | Local            |
| **File Observer** | Watchdog                    | Detect file changes             | Local            |
| **Delta Cache**   | Redis                       | SHA-256 hash caching            | Local Docker     |
| **Orchestration** | LangGraph                   | Coordinate processing workflows | Local            |
| **Parser**        | Python AST                  | Structural code parsing         | Local            |
| **Metadata DB**   | SQLite                      | AST metadata and relationships  | Local            |
| **Embeddings**    | Ollama + `nomic-embed-text` | Local code embeddings           | Local            |
| **Vector DB**     | ChromaDB                    | Semantic code search            | Local            |
| **Security**      | Ollama + `llama-guard3:1b`  | Prompt/security filtering       | Local            |
| **Reasoning**     | Gemini Flash                | Final reasoning                 | Google AI Studio |
| **Observability** | LangSmith                   | Tracing and latency analysis    | Free Tier        |
| **Benchmarking**  | Locust                      | Load and throughput testing     | Local            |

---

# 💰 $0-Budget Design

The project is designed to operate without paid infrastructure.

### Local

The following components run locally:

* Python
* Watchdog
* Redis
* SQLite
* ChromaDB
* Ollama
* `nomic-embed-text`
* `llama-guard3:1b`
* LangGraph
* Click
* Rich
* LangSmith

### Free Tier

The reasoning layer uses:

* Google AI Studio
* Gemini Flash

Observability can use free-tier options such as:

* LangSmith

> API quotas and free-tier limits are subject to the respective service providers and may change over time.

---

# 📋 Requirements

* Python 3.10+
* Ollama
* Docker
* Redis
* Google AI Studio API key
* Git

---

# 🧰 Prerequisites

## 1. Install Ollama

Install and start Ollama on your system.

Verify the installation:

```bash
ollama --version
```

## 2. Pull the Embedding Model

`logan` uses Ollama's **`nomic-embed-text`** model locally to generate code embeddings.

```bash
ollama pull nomic-embed-text
```

## 3. Pull the Security Model

`logan` uses **`llama-guard3:1b`** locally through Ollama for prompt and security filtering.

```bash
ollama pull llama-guard3:1b
```

## 4. Start Redis

Run Redis using Docker:

```bash
docker run -d -p 6379:6379 redis:alpine
```

Verify:

```bash
docker ps
```

## 5. Configure Gemini

Create a Google AI Studio API key and add it to your environment:

```env
GOOGLE_API_KEY=your_google_ai_studio_api_key
```

Do not commit API keys or other secrets to Git.

---

# 📦 Installation

## 1. Clone the repository

```bash
git clone https://github.com/your-username/logan.git
cd logan
```

## 2. Create a virtual environment

```bash
python -m venv .venv
```

### Linux / macOS

```bash
source .venv/bin/activate
```

### Windows

```bash
.venv\Scripts\activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Install the CLI

If the project is packaged as an editable Python package:

```bash
pip install -e .
```

The CLI command should then be available as:

```bash
logan
```

---

# 🚀 Usage

Start the interactive agent:

```bash
logan
```

Example:

```text
logan ❯ explain how the indexing pipeline works
```

Other example queries:

```text
logan ❯ where is Redis initialized?

logan ❯ explain how file changes are detected

logan ❯ find the function responsible for prompt validation

logan ❯ how are ChromaDB and SQLite used together?

logan ❯ explain the security flow before retrieval
```

---

# 📊 Observability & Benchmarking

The system can be instrumented to trace the performance of individual pipeline stages.

Tracing can be implemented using LangSmith:
<img width="1390" height="913" alt="image" src="https://github.com/user-attachments/assets/0d3a809b-2d19-4e91-8e71-918276ba3cc0" />

# ⚠️ Version 1.0 Limitations

### Python-Only Support

The current AST indexing pipeline is designed for Python source files.

### Local Hardware Usage

The embedding and security models run locally through Ollama and consume CPU/RAM resources.

### LlamaGuard Resource Requirements

The security model can require significantly more memory than the lightweight embedding model.

### Semantic Retrieval Limitations

Vector search can occasionally retrieve semantically similar but incorrect code, especially in repositories containing many similarly named functions or modules.

### Gemini Dependency

Final reasoning currently depends on the Gemini API.

The indexing, embedding, caching, security filtering, and retrieval stages remain local.

### Free-Tier Limits

Gemini usage is subject to the current Google AI Studio API quotas and limits.

### Initial Indexing

The initial indexing process can take longer for large repositories because the files must be parsed and embedded before semantic search becomes available.

---

# 🔮 Future Improvements

Potential future versions could introduce:

* 🌐 **React Web Interface** — Visual codebase exploration and search.
* 🌲 **Multi-Language Support** — Tree-sitter-based parsing for JavaScript, TypeScript, Go, Rust, and other languages.
* 🔎 **BM25 + Vector Retrieval** — Combine sparse keyword retrieval with dense embeddings.
* 🧠 **Re-Ranking** — Add a dedicated re-ranking stage for improved retrieval precision.
* 🔗 **Dependency Graph Retrieval** — Follow relationships between modules, functions, classes, and imports.
* 🤖 **Fully Local Reasoning** — Replace Gemini with a local reasoning/coding model through Ollama.
* 📈 **Benchmark Dashboard** — Visualize latency, throughput, and retrieval metrics.
* 🔐 **Expanded Security Policies** — Add more granular controls for sensitive files and directories.
* ⚡ **Advanced Incremental Indexing** — Further optimize indexing for very large repositories.

---

---

# 🧠 Design Philosophy

`logan` is built around four main principles:

### 1. Keep the Codebase Local

The repository is indexed and searched locally rather than being repeatedly uploaded as a whole to a cloud model.

### 2. Process Only What Changed

SHA-256 hashing and Redis caching prevent unchanged files from being unnecessarily re-parsed and re-embedded.

### 3. Retrieve Before Reasoning

The reasoning model receives relevant code context rather than the entire repository.

### 4. Security Before Access

Incoming prompts pass through local security checks before triggering filesystem or database lookups.

Together, these principles form the core `logan` pipeline:

```text
                 Local Codebase
                       │
                       ▼
                  Watchdog
                       │
                       ▼
                   SHA-256
                       │
                       ▼
                    Redis
                       │
                Changed Files
                       │
                       ▼
                  AST Parser
                       │
              ┌────────┴────────┐
              ▼                 ▼
           SQLite           ChromaDB
              │                 │
              └────────┬────────┘
                       │
                       ▼
                  User Prompt
                       │
                       ▼
                  LlamaGuard
                       │
                       ▼
                Local Retrieval
                       │
                       ▼
                Relevant Context
                       │
                       ▼
                 Gemini Flash
                       │
                       ▼
                   Response
```

---

<img width="1447" height="465" alt="Screenshot 2026-09-20 221547" src="https://github.com/user-attachments/assets/40bd1de7-8a76-488d-8e63-04bac9238795" />
(Logan Answering query)
<img width="1431" height="225" alt="Screenshot 2026-09-20 223405" src="https://github.com/user-attachments/assets/5d90b95a-be14-4a2d-b13c-ff93e22546ee" />
(Security Block)




# 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
