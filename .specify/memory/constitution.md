# Memoria Project Constitution

## Core Principles

### I. Clean Architecture (Onion Model)

Memoria follows strict clean architecture with three layers:
- **Domain Layer**: Immutable entities (frozen dataclasses), ports (interfaces). NO external dependencies.
- **Adapters Layer**: Implements ports, integrates with external systems (ChromaDB, sentence-transformers). Dependencies allowed here.
- **Application Layer**: Orchestration logic in skill_helpers.py. Composes adapters to provide high-level operations.

**Rules**:
- Domain depends on NOTHING (zero imports from adapters or application)
- Adapters depend on domain (import ports and entities)
- Application depends on adapters and domain
- NO circular dependencies between layers

### II. Immutability & Thread Safety

All domain entities MUST be immutable (frozen dataclasses):
- Document: Represents RAG document with content, metadata, embedding
- SearchResult: Represents query match with document, score, rank
- Embedding: Represents vector embedding (if defined as entity)

**Rules**:
- Use `@dataclass(frozen=True)` for all entities
- Entities include `__post_init__()` validation of invariants
- NO mutation after creation - create new instances instead
- Thread safety guaranteed through immutability

### III. Adapter Pattern (Port-Adapter Architecture)

All external dependencies isolated behind ports (interfaces):
- **VectorStorePort**: ChromaDB operations (search, add_documents, count)
- **EmbeddingGeneratorPort**: Sentence-transformer operations (embed_text, embed_texts_batch)
- **SearchEnginePort**: Hybrid search (semantic + BM25 keyword search)
- **DocumentProcessorPort**: Document chunking and preprocessing

**Rules**:
- Ports defined in `memoria/domain/ports/`
- Adapters in `memoria/adapters/` (chromadb, sentence_transformers, search, document)
- Adapter constructors accept configuration parameters (collection_name, model_name, hybrid_weight, etc.)
- NO hard-coded configuration - use constructor parameters or environment variables

### IV. Backward Compatibility (NON-NEGOTIABLE)

Public API in `skill_helpers.py` MUST remain stable:
- **search_knowledge(query, mode, expand, limit)**: RAG search interface
- **add_document(file_path, reindex)**: Single document indexing
- **index_documents(pattern, rebuild)**: Bulk document indexing
- **list_indexed_documents()**: Query indexed documents
- **get_stats()**: System statistics
- **health_check()**: System health verification

**Rules**:
- NO changes to function signatures (parameter names, order, defaults)
- NO removal of functions
- Internal implementation changes ALLOWED (optimize algorithms, change adapters)
- Existing client code must continue working without modification

### V. Performance Requirements

System MUST meet these performance targets:
- **Search**: Query response time <2 seconds for 90% of queries against 2000+ document collections
- **Indexing**: Throughput ≥20 documents/minute for typical document sizes (10-100KB)
- **Memory**: Peak memory usage <2GB during batch indexing operations
- **Reliability**: 0% timeout rate for batch indexing of 100 documents

**Rules**:
- Profile performance before optimization (measure, don't guess)
- Use diagnostic scripts for validation (specs/*/diagnostics/)
- Document performance characteristics in README and code comments
- Optimize adapter implementations, NOT domain entities

### VI. Testing Strategy

Focus on integration and acceptance testing due to external dependencies:
- **Integration Tests**: Test adapter implementations against real ChromaDB and sentence-transformers
- **Acceptance Tests**: Test user stories end-to-end with real document collections
- **Performance Tests**: Validate success criteria (SC-001 through SC-007) with benchmark scripts
- **Diagnostic Scripts**: Interactive debugging tools in specs/*/diagnostics/

**Rules**:
- Tests located in `tests/` directory (integration/, acceptance/, performance/)
- Diagnostic scripts in `specs/[spec-number]/diagnostics/`
- Use existing ChromaDB Docker container (port 8001) for integration tests
- Document test execution procedures in quickstart.md

## Architecture Constraints

### Technology Stack

- **Language**: Python 3.11+
- **Vector Database**: ChromaDB 0.4.x (HTTP mode, Docker container on port 8001)
- **Embedding Model**: sentence-transformers all-MiniLM-L6-v2 (384 dimensions)
- **Chunking**: LangChain RecursiveCharacterTextSplitter (2000 chars, 100 overlap)
- **Search Algorithm**: Hybrid search (95% semantic cosine similarity, 5% BM25 keyword)

### Configuration Management

Configuration passed via adapter constructors:
- ChromaDBAdapter: collection_name, use_http, http_host, http_port, db_path
- SentenceTransformerAdapter: model_name
- SearchEngineAdapter: hybrid_weight (default 0.95)
- DocumentProcessorAdapter: chunk_size, chunk_overlap

**NO global configuration files** - all config explicit in code or environment variables.

### Data Persistence

- **Vector embeddings**: ChromaDB (Docker volume persistence)
- **Document storage**: ChromaDB metadata (original content and source path)
- **No separate database**: ChromaDB is single source of truth

## Development Workflow

### Investigation-First Approach

For performance work, MUST complete investigation BEFORE implementation:
1. Create diagnostic infrastructure (scripts, baseline tests)
2. Collect baseline metrics (current performance)
3. Identify root cause through empirical testing
4. Document findings in specs/[spec-number]/research.md
5. Design fix based on evidence, not assumptions
6. Implement and validate with same diagnostic tools

**Rules**:
- NO premature optimization without measurements
- Diagnostic scripts MUST be created first (reusable for validation)
- Root cause analysis documented before code changes
- Success criteria defined upfront, validated after implementation

### Incremental Delivery (MVP-First)

Complex features delivered incrementally:
1. **Setup Phase**: Constitution, diagnostic infrastructure, baseline data
2. **MVP Phase**: Fix most critical user story (e.g., US1 - multi-result search)
3. **Incremental Phases**: Add remaining user stories one at a time
4. **Polish Phase**: Documentation, performance monitoring, final validation

**Rules**:
- Each increment independently testable and deployable
- Validate before proceeding to next increment
- User stories prioritized (P1 before P2, critical before nice-to-have)
- Stop and review after MVP delivery (adjust plan based on findings)

### Code Change Scope

Focus changes narrowly on adapters layer:
- **ChromaDBAdapter**: Batch operations, timeout configuration, query optimization
- **SentenceTransformerAdapter**: Batch embedding API, model optimization
- **SearchEngineAdapter**: Hybrid search weighting, result ranking
- **DocumentProcessorAdapter**: Chunking strategy optimization
- **skill_helpers.py**: Orchestration logic (progressive batching, progress tracking)

**Rules**:
- NO changes to domain entities (Document, SearchResult are stable)
- NO changes to port interfaces (breaking change to adapters)
- Optimize implementations, NOT interfaces
- Preserve clean architecture boundaries

## Governance

### Constitution Authority

This constitution supersedes all other practices and decisions:
- All code changes MUST comply with architecture principles
- All PRs MUST verify backward compatibility (run existing test suite)
- All performance work MUST follow investigation-first approach
- Complexity violations REQUIRE explicit justification and documentation

### Quality Gates

Before merging:
1. ✅ All existing tests pass (integration + acceptance)
2. ✅ Public API unchanged (skill_helpers.py functions)
3. ✅ Performance targets met (validate with diagnostic scripts)
4. ✅ No domain layer violations (entities remain immutable, no external dependencies)
5. ✅ Documentation updated (README, quickstart.md, code comments)

### Amendments

Constitution changes require:
1. Documentation of WHY change is necessary
2. Impact analysis on existing architecture
3. Migration plan for affected code
4. Approval from project maintainer
5. Update to constitution version and last amended date

**Version**: 1.0.0 | **Ratified**: 2026-01-31 | **Last Amended**: 2026-01-31
