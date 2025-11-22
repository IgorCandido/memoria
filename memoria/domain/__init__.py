"""
Domain layer - Core business logic with zero external dependencies.

This layer contains:
- Entities: Core domain objects (Document, SearchResult, Chunk)
- Value Objects: Immutable value types (Score, Embedding, QueryTerms)
- Domain Services: Pure business logic
- Ports: Protocol interfaces that adapters must implement

Dependencies: NONE - this layer depends on nothing external.
"""
