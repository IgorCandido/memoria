"""Skill Helpers - High-Level API for Claude Code"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import io

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
        _search_engine = SearchEngineAdapter(_vector_store, _embedder, hybrid_weight=0.7)
        _document_processor = DocumentProcessorAdapter(chunk_size=1000, chunk_overlap=200)

    return _vector_store, _embedder, _search_engine, _document_processor


def search_knowledge(query, mode="hybrid", expand=True, limit=5):
    vector_store, embedder, search_engine, _ = _get_adapters()
    results = search_engine.search(query=query, limit=limit, mode="hybrid" if mode == "hybrid" else "semantic")

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

    return console.file.getvalue()


def index_documents(pattern="**/*.md", rebuild=False):
    """
    Index documents from the docs folder into ChromaDB.

    NOTE: Partial/incremental indexing is not yet supported (Phase 4 feature).
    Currently always re-indexes all matching documents.

    Args:
        pattern: Glob pattern for documents to index (default: "**/*.md")
        rebuild: Ignored for now - always rebuilds (Phase 4 will implement this)
    """
    vector_store, embedder, _, doc_processor = _get_adapters()
    console = Console(file=io.StringIO(), force_terminal=False, width=120)

    try:
        docs_list = [f for f in DOCS_DIR.glob(pattern) if f.is_file()]
        if not docs_list:
            console.print("[yellow]⚠️  No documents[/yellow]")
            return console.file.getvalue()

        console.print(f"Found {len(docs_list)} documents")

        # Note: Partial indexing will be implemented in Phase 4
        # For now, always process all documents

        all_documents = []
        for i, doc_path in enumerate(docs_list, 1):
            console.print(f"[{i}/{len(docs_list)}] Processing {doc_path.name}...")
            # process_document expects Path object and returns list[Document]
            documents_without_embeddings = doc_processor.process_document(doc_path)

            # Generate embeddings and create new Documents (frozen dataclass - can't modify after creation)
            for doc in documents_without_embeddings:
                embedding = embedder.embed_text(doc.content)
                # Create new Document with embedding at construction time
                from memoria.domain.entities import Document
                new_doc = Document(
                    id=doc.id,
                    content=doc.content,
                    embedding=embedding.to_list(),  # Convert Embedding value object to list[float]
                    metadata=doc.metadata
                )
                all_documents.append(new_doc)

        console.print(f"Generated {len(all_documents)} document chunks")
        console.print("Adding to database...")
        vector_store.add_documents(all_documents)

        console.print("✓ Build complete\n")
        console.print("[bold green]✅ Indexing Complete[/bold green]\n")
        console.print(f"[cyan]Documents:[/cyan] {len(docs_list)}")
        console.print(f"[cyan]Chunks:[/cyan] {len(all_documents)}")

    except Exception as e:
        console.print(f"[red]❌ Failed: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")

    return console.file.getvalue()


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
