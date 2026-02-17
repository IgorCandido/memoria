"""Skill Helpers - High-Level API for Claude Code"""

from pathlib import Path
import io
import json
import os
import threading

# Try to import rich, but provide fallbacks if not available
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

    # Simple fallback implementations
    class Console:
        def __init__(self, file=None, force_terminal=False, width=120):
            self.file = file or io.StringIO()

        def print(self, *args, **kwargs):
            # Strip Rich markup for plain text
            import re
            text = ' '.join(str(arg) for arg in args)
            text = re.sub(r'\[/?[^\]]+\]', '', text)  # Remove [bold], [cyan], etc.
            print(text, file=self.file)

    class Table:
        def __init__(self, **kwargs):
            self.rows = []
            self.columns = []

        def add_column(self, name, **kwargs):
            self.columns.append(name)

        def add_row(self, *values):
            self.rows.append(values)

    class Panel:
        def __init__(self, content, **kwargs):
            self.content = content

        def __str__(self):
            import re
            text = re.sub(r'\[/?[^\]]+\]', '', str(self.content))
            return f"\n{'=' * 60}\n{text}\n{'=' * 60}\n"

# Import adapters directly
from memoria.adapters.chromadb.chromadb_adapter import ChromaDBAdapter
from memoria.adapters.sentence_transformers.sentence_transformer_adapter import SentenceTransformerAdapter
from memoria.adapters.search.search_engine_adapter import SearchEngineAdapter
from memoria.adapters.document.document_processor_adapter import DocumentProcessorAdapter

# Paths
MEMORIA_ROOT = Path(__file__).parent.parent
DOCS_DIR = MEMORIA_ROOT / "docs"
CHROMA_DIR = MEMORIA_ROOT / "chroma_data"

# Global adapter instances
_vector_store = None
_embedder = None
_search_engine = None
_document_processor = None

# Version check state (module-level, reset per Python process / session)
_version_checked = False
_version_check_thread = None

# Version check constants
_VERSION_CACHE_PATH = Path.home() / ".local" / "share" / "memoria" / ".version-cache"
_VERSION_CACHE_TTL_HOURS = 24
_GH_TIMEOUT_SECONDS = 5


def _get_adapters():
    global _vector_store, _embedder, _search_engine, _document_processor

    if _vector_store is None:
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        # HTTP mode for Docker ChromaDB
        _vector_store = ChromaDBAdapter(
            collection_name="memoria",
            use_http=True,
            http_host="localhost",
            http_port=8001,
        )

        _embedder = SentenceTransformerAdapter(model_name="all-MiniLM-L6-v2")
        _search_engine = SearchEngineAdapter(_vector_store, _embedder, hybrid_weight=0.95)
        _document_processor = DocumentProcessorAdapter(chunk_size=2000, chunk_overlap=100)

    return _vector_store, _embedder, _search_engine, _document_processor


def _check_version_cache():
    """Read version cache file, return dict or None if stale/missing."""
    try:
        if not _VERSION_CACHE_PATH.exists():
            return None

        with open(_VERSION_CACHE_PATH) as f:
            data = json.load(f)

        checked_at = data.get("checked_at", "")
        if not checked_at:
            return None

        from datetime import datetime, timezone
        dt = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600

        if age_hours > _VERSION_CACHE_TTL_HOURS:
            return None

        return data
    except Exception:
        return None


def _update_version_cache():
    """Query GitHub releases API via subprocess, update cache file."""
    import subprocess
    try:
        result = subprocess.run(
            ["gh", "api", "repos/IgorCandido/memoria/releases/latest", "--jq", ".tag_name"],
            capture_output=True, text=True, timeout=_GH_TIMEOUT_SECONDS
        )
        if result.returncode != 0:
            return

        latest_version = result.stdout.strip().lstrip("v")
        if not latest_version:
            return

        # Read current version
        current_version = ""
        version_file = MEMORIA_ROOT / "VERSION"
        if version_file.exists():
            current_version = version_file.read_text().strip()

        from datetime import datetime, timezone
        cache_data = {
            "latest_version": latest_version,
            "current_version": current_version,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "cache_ttl_hours": _VERSION_CACHE_TTL_HOURS,
            "update_available": latest_version != current_version,
            "notification_shown": False,
            "check_error": None,
        }

        _VERSION_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_VERSION_CACHE_PATH, "w") as f:
            json.dump(cache_data, f, indent=2)

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # gh not available, network timeout, or filesystem error — silently ignore
        pass
    except Exception:
        pass


def _should_notify_update():
    """Check if user should be notified about available update."""
    cache = _check_version_cache()
    if cache is None:
        return False, ""

    if not cache.get("update_available", False):
        return False, ""

    if cache.get("notification_shown", False):
        return False, ""

    return True, cache.get("latest_version", "")


def _mark_notification_shown():
    """Mark that the update notification has been shown this cache cycle."""
    try:
        if not _VERSION_CACHE_PATH.exists():
            return

        with open(_VERSION_CACHE_PATH) as f:
            data = json.load(f)

        data["notification_shown"] = True

        with open(_VERSION_CACHE_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def search_knowledge(query, mode="hybrid", expand=True, limit=5):
    global _version_checked, _version_check_thread
    import time as _time

    # Version check on first call per session (non-blocking)
    if not _version_checked:
        _version_checked = True
        cache = _check_version_cache()
        if cache is None:
            _version_check_thread = threading.Thread(
                target=_update_version_cache, daemon=True
            )
            _version_check_thread.start()

    vector_store, embedder, search_engine, _ = _get_adapters()

    _perf_start = _time.time()
    results = search_engine.search(query=query, limit=limit, mode="hybrid" if mode == "hybrid" else "semantic")
    _perf_elapsed = (_time.time() - _perf_start) * 1000  # ms

    if os.getenv("MEMORIA_DEBUG"):
        print(f"[PERF] search_knowledge: query_time={_perf_elapsed:.1f}ms, "
              f"results={len(results)}, mode={mode}, limit={limit}")

    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    console.print(f"\n[bold cyan]📚 Search Results for \"{query}\"[/bold cyan]\n")

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        return console.file.getvalue()

    for i, result in enumerate(results, 1):
        # SearchResult has .document.content, not .content directly
        content = result.document.content
        source = result.document.metadata.get("source", "unknown")
        score = result.score

        if len(content) > 500:
            content = content[:500] + "..."

        console.print(f"[bold]Result {i}[/bold] (Score: {score:.2f})")
        console.print(f"[dim]Source:[/dim] {source}")
        console.print(Panel(content, border_style="dim", padding=(0, 1)))
        console.print()

    # Append update notification if available (non-blocking, shown once)
    should_notify, latest = _should_notify_update()
    if should_notify:
        console.print(f"\n[dim]ℹ️  Memoria v{latest} available. Run: memoria update[/dim]")
        _mark_notification_shown()

    return console.file.getvalue()


def index_documents(pattern="**/*.md", rebuild=False):
    """
    Index documents from the docs folder into ChromaDB.

    Uses batch embedding for efficient processing and progressive batching
    to commit chunks to ChromaDB every COMMIT_BATCH_SIZE chunks, preventing
    timeouts and memory exhaustion with large collections.

    Handles individual document failures gracefully - continues indexing
    remaining documents and reports failures in the summary.

    Args:
        pattern: Glob pattern for documents to index (default: "**/*.md")
        rebuild: Ignored for now - always rebuilds (Phase 4 will implement this)
    """
    from memoria.domain.entities import Document, ProgressTracker

    COMMIT_BATCH_SIZE = 500  # Commit to ChromaDB every N chunks (balances memory vs commit overhead)

    vector_store, embedder, _, doc_processor = _get_adapters()
    console = Console(file=io.StringIO(), force_terminal=False, width=120)

    try:
        docs_list = [f for f in DOCS_DIR.glob(pattern) if f.is_file()]
        if not docs_list:
            console.print("[yellow]⚠️  No documents[/yellow]")
            return console.file.getvalue()

        console.print(f"Found {len(docs_list)} documents")
        tracker = ProgressTracker(total_documents=len(docs_list))

        pending_chunks = []  # Chunks waiting for embedding + commit
        total_chunks_committed = 0

        for i, doc_path in enumerate(docs_list, 1):
            tracker.current_document = doc_path.name
            console.print(f"[{i}/{len(docs_list)}] Processing {doc_path.name}...")

            try:
                documents_without_embeddings = doc_processor.process_document(doc_path)
                pending_chunks.extend(documents_without_embeddings)
                tracker.mark_processed(doc_path.name)
            except Exception as doc_err:
                tracker.mark_failed(doc_path.name, str(doc_err))
                console.print(f"[yellow]⚠️  Skipped {doc_path.name}: {doc_err}[/yellow]")
                continue

            # Progressive batching: commit when we have enough chunks
            if len(pending_chunks) >= COMMIT_BATCH_SIZE:
                committed = _embed_and_commit_batch(
                    pending_chunks, embedder, vector_store, console
                )
                total_chunks_committed += committed
                pending_chunks = []

        # Commit remaining chunks
        if pending_chunks:
            committed = _embed_and_commit_batch(
                pending_chunks, embedder, vector_store, console
            )
            total_chunks_committed += committed

        tracker.finish()
        elapsed = tracker.elapsed_seconds
        throughput = tracker.docs_per_minute

        console.print("✓ Build complete\n")
        console.print("[bold green]✅ Indexing Complete[/bold green]\n")
        console.print(f"[cyan]Documents:[/cyan] {tracker.processed_documents}")
        console.print(f"[cyan]Chunks:[/cyan] {total_chunks_committed}")
        console.print(f"[cyan]Throughput:[/cyan] {throughput:.1f} docs/min")
        console.print(f"[cyan]Duration:[/cyan] {elapsed:.1f}s")

        if tracker.failed_documents > 0:
            console.print(f"\n[yellow]⚠️  Failed documents ({tracker.failed_documents}):[/yellow]")
            for filename, error in tracker.failed_files:
                console.print(f"[yellow]  - {filename}: {error}[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Failed: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

    return console.file.getvalue()


def _embed_and_commit_batch(chunks, embedder, vector_store, console):
    """
    Embed a batch of document chunks and commit them to ChromaDB.

    Uses batch embedding API for efficient processing.

    Args:
        chunks: List of Document objects without embeddings
        embedder: SentenceTransformerAdapter instance
        vector_store: ChromaDBAdapter instance
        console: Console for logging

    Returns:
        Number of chunks successfully committed
    """
    from memoria.domain.entities import Document

    if not chunks:
        return 0

    console.print(f"  Embedding {len(chunks)} chunks...")

    try:
        # Extract texts for batch embedding
        texts = [doc.content for doc in chunks]

        # Use batch embedding API (much faster than sequential)
        embeddings = embedder.embed_batch(texts)

        # Create Document objects with embeddings
        docs_with_embeddings = []
        for doc, embedding in zip(chunks, embeddings):
            new_doc = Document(
                id=doc.id,
                content=doc.content,
                embedding=embedding.to_list(),
                metadata=doc.metadata,
            )
            docs_with_embeddings.append(new_doc)

        console.print(f"  Committing {len(docs_with_embeddings)} chunks to database...")
        vector_store.add_documents(docs_with_embeddings)

        return len(docs_with_embeddings)

    except Exception as e:
        console.print(f"[red]⚠️  Batch commit failed ({len(chunks)} chunks): {e}[/red]")
        return 0


def add_document(file_path, reindex=True):
    import shutil
    source_path = Path(file_path)
    if not source_path.exists():
        return f"❌ Not found: {file_path}"
    
    dest_path = DOCS_DIR / source_path.name
    if dest_path.exists():
        return f"⚠️  Already exists: {source_path.name}"
    
    shutil.copy2(source_path, dest_path)
    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    console.print(f"\n[green]✅ Added:[/green] {source_path.name}")
    
    if reindex:
        console.print("[cyan]Re-indexing...[/cyan]")
        index_documents()
        console.print("[green]✅ Done[/green]\n")
    
    return console.file.getvalue()


def list_indexed_documents():
    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    files = [f for f in DOCS_DIR.rglob("*") if f.is_file()]
    console.print(f"\n[bold cyan]📄 Documents ({len(files)} files)[/bold cyan]\n")
    
    if not files:
        console.print("[yellow]No documents[/yellow]")
        return console.file.getvalue()

    by_dir = {}
    for file_path in sorted(files):
        rel_path = file_path.relative_to(DOCS_DIR)
        parent = str(rel_path.parent) if rel_path.parent != Path(".") else "root"
        if parent not in by_dir:
            by_dir[parent] = []
        by_dir[parent].append(rel_path)

    for dir_name, file_list in sorted(by_dir.items()):
        console.print(f"[bold]{dir_name}/[/bold]")
        for fp in sorted(file_list):
            console.print(f"  - {fp.name}")
        console.print()

    return console.file.getvalue()


def get_stats():
    vector_store, _, _, _ = _get_adapters()
    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    console.print("\n[bold cyan]📊 Stats[/bold cyan]\n")

    try:
        count = vector_store._collection.count()
        table = Table(show_header=False, box=None)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Chunks", str(count))
        table.add_row("Database", "ChromaDB (HTTP)")
        table.add_row("Collection", vector_store.collection_name)
        console.print(table)
    except Exception as e:
        console.print(f"[red]❌ {e}[/red]")

    return console.file.getvalue()


def check_unindexed_documents(pattern="**/*.md"):
    """
    Check which documents in docs/ are not yet indexed in RAG.

    Args:
        pattern: Glob pattern for files to check (default: all markdown)

    Returns:
        List of relative paths to unindexed documents
    """
    vector_store, _, _, _ = _get_adapters()

    # Get all matching files
    all_docs = [f for f in DOCS_DIR.glob(pattern) if f.is_file()]

    # Get indexed sources from ChromaDB
    try:
        collection = vector_store.get_collection()
        all_metadata = collection.get()['metadatas']
        indexed_sources = {m.get('source') for m in all_metadata if m.get('source')}
    except Exception:
        # If ChromaDB query fails, assume nothing indexed
        indexed_sources = set()

    # Find unindexed
    unindexed = []
    for doc_path in all_docs:
        rel_path = str(doc_path.relative_to(MEMORIA_ROOT))
        if rel_path not in indexed_sources:
            unindexed.append(rel_path)

    return unindexed


def auto_index_new_documents(pattern="**/*.md"):
    """
    Automatically index any unindexed documents in docs/ directory.

    Args:
        pattern: Glob pattern for files to index (default: all markdown)

    Returns:
        Formatted output string showing what was indexed
    """
    console = Console(file=io.StringIO(), force_terminal=False, width=120)

    unindexed = check_unindexed_documents(pattern)

    if not unindexed:
        console.print("[green]✅ All documents already indexed[/green]")
        return console.file.getvalue()

    console.print(f"[yellow]📚 Found {len(unindexed)} unindexed documents[/yellow]")

    for doc in unindexed:
        console.print(f"[dim]  • {doc}[/dim]")

    console.print("\n[cyan]Indexing now...[/cyan]\n")

    # Use index_documents with rebuild=False (it will only process these files)
    result = index_documents(pattern=pattern, rebuild=False)
    console.print(result)

    return console.file.getvalue()


def health_check():
    console = Console(file=io.StringIO(), force_terminal=False, width=120)
    console.print("\n[bold cyan]🏥 Health Check[/bold cyan]\n")

    try:
        vector_store, _, _, _ = _get_adapters()
        count = vector_store._collection.count()
        
        table = Table(show_header=False, box=None)
        table.add_column("Component", style="cyan")
        table.add_column("Status")
        table.add_row("RAG System", "[green]✅ Healthy[/green]")
        table.add_row("ChromaDB", f"[green]✅ Connected ({count} chunks)[/green]")
        table.add_row("Docs", f"[green]✅ {len([f for f in DOCS_DIR.rglob('*') if f.is_file()])} files[/green]")
        console.print(table)
    except Exception as e:
        console.print(f"[red]❌ Failed: {e}[/red]")

    return console.file.getvalue()
