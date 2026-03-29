#!/usr/bin/env python3
"""Memoria CLI - RAG knowledge base interface."""
import argparse
import json
import sys


MEMORIA_ROOT = "/Users/igorcandido/Github/thinker/memoria/main"


def cmd_search(args):
    from memoria.skill_helpers import search_knowledge
    print(search_knowledge(query=args.query, mode=args.mode, limit=args.limit))


def cmd_store(args):
    from memoria.skill_helpers import store_document
    content = args.content
    if content == "-":
        content = sys.stdin.read()
    print(store_document(content=content, source_id=args.source_id, title=args.title))


def cmd_get(args):
    from memoria.skill_helpers import get_document
    print(get_document(args.source_id))


def cmd_delete(args):
    from memoria.skill_helpers import delete_document
    print(delete_document(args.source_id))


def cmd_list(args):
    from memoria.skill_helpers import list_documents
    docs = list_documents()
    for doc in docs:
        print(f"{doc.source_id}\tv{doc.version}\t{doc.title}")


def cmd_health(args):
    from memoria.skill_helpers import health_check
    print(health_check())


def cmd_stats(args):
    from memoria.skill_helpers import get_stats
    print(get_stats())


def cmd_export(args):
    from memoria.skill_helpers import export_corpus
    print(export_corpus(args.output))


def cmd_import(args):
    from memoria.skill_helpers import import_corpus
    result = import_corpus(args.input)
    print(f"added={result.documents_added} updated={result.documents_updated} "
          f"skipped={result.documents_skipped} failed={result.documents_failed} "
          f"duration={result.duration_seconds:.1f}s")
    if result.errors:
        for source_id, err in result.errors:
            print(f"  ERROR: {source_id}: {err}", file=sys.stderr)


def cmd_reindex(args):
    from memoria.skill_helpers import reindex_corpus
    result = reindex_corpus()
    print(f"processed={result.documents_processed} chunks={result.chunks_created} "
          f"failed={result.documents_failed} duration={result.duration_seconds:.1f}s "
          f"model={result.embedding_model}")


def main():
    parser = argparse.ArgumentParser(prog="memoria", description="RAG knowledge base CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # search
    p = sub.add_parser("search", help="Search the knowledge base")
    p.add_argument("query", help="Search query")
    p.add_argument("--mode", default="hybrid", choices=["hybrid", "semantic", "keyword"])
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(func=cmd_search)

    # store
    p = sub.add_parser("store", help="Store a document")
    p.add_argument("source_id", help="Unique document identifier")
    p.add_argument("content", help="Document content (use '-' for stdin)")
    p.add_argument("--title", help="Document title (defaults to source_id)")
    p.set_defaults(func=cmd_store)

    # get
    p = sub.add_parser("get", help="Retrieve a document by source_id")
    p.add_argument("source_id")
    p.set_defaults(func=cmd_get)

    # delete
    p = sub.add_parser("delete", help="Delete a document")
    p.add_argument("source_id")
    p.set_defaults(func=cmd_delete)

    # list
    p = sub.add_parser("list", help="List all documents")
    p.set_defaults(func=cmd_list)

    # health
    p = sub.add_parser("health", help="Health check")
    p.set_defaults(func=cmd_health)

    # stats
    p = sub.add_parser("stats", help="Show stats")
    p.set_defaults(func=cmd_stats)

    # export
    p = sub.add_parser("export", help="Export corpus to JSONL")
    p.add_argument("output", help="Output file path")
    p.set_defaults(func=cmd_export)

    # import
    p = sub.add_parser("import", help="Import corpus from JSONL")
    p.add_argument("input", help="Input file path")
    p.set_defaults(func=cmd_import)

    # reindex
    p = sub.add_parser("reindex", help="Reindex all documents")
    p.set_defaults(func=cmd_reindex)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
