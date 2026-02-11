# Feature Specification: Configurable Embedding Models

**Feature Branch**: `004-configurable-embeddings`
**Created**: 2026-02-11
**Status**: FUTURE - Not started, defined for later prioritization
**Motivation**: Fix SC-002 from spec 002 (confidence score range 0.029, needs 0.4+)

## Background

Memoria currently hardcodes `all-MiniLM-L6-v2` (384 dimensions) as the embedding model via `SentenceTransformerAdapter`. This lightweight model produces compressed score distributions on large homogeneous corpora (18K chunks of technical docs), making confidence scores cluster tightly (range ~0.029 instead of target 0.4+).

A dedicated RTX 5060 Ti 16GB GPU is available on relishhost2 (192.168.1.171:11434) running Ollama, with existing client infrastructure in place. This enables running larger, higher-quality embedding models that may produce better score separation.

## Existing Infrastructure

| Component | Location | Purpose |
|-----------|----------|---------|
| EmbeddingGeneratorPort | `memoria/domain/ports/embedding_generator.py` | Port interface (Protocol class) |
| SentenceTransformerAdapter | `memoria/adapters/sentence_transformers/sentence_transformer_adapter.py` | Current adapter (all-MiniLM-L6-v2) |
| EmbeddingGeneratorStub | `memoria/adapters/stubs/embedding_generator_stub.py` | Test stub |
| ollamaLocal client | `~/Github/thinker/ollamaLocal/skill/ollama_client.py` | HTTP client to relishhost2:11434 |
| ollama_http_client | `~/Github/thinker/localAgent/src/agent/ollama_http_client.py` | macOS subprocess curl wrapper |
| Ollama on relishhost2 | 192.168.1.171:11434 | RTX 5060 Ti 16GB, Docker, NVIDIA runtime |

## User Scenarios & Testing

### User Story 1 - Configurable Embedding Model Selection (Priority: P1)

As a memoria operator, I want to configure which embedding model is used so that I can test different models and find the best score distribution for my corpus.

**Why this priority**: Core enabler - all other stories depend on model being configurable.

**Independent Test**: Set `MEMORIA_EMBEDDING_MODEL=nomic-embed-text` and `MEMORIA_EMBEDDING_BACKEND=ollama`, run a search query, verify embeddings come from Ollama on relishhost2.

**Acceptance Scenarios**:

1. **Given** default config (no env vars set), **When** memoria starts, **Then** it uses `all-MiniLM-L6-v2` via SentenceTransformer (backward compatible)
2. **Given** `MEMORIA_EMBEDDING_BACKEND=ollama` and `MEMORIA_EMBEDDING_MODEL=nomic-embed-text`, **When** memoria starts, **Then** it uses Ollama API on relishhost2 for embeddings
3. **Given** Ollama is unreachable, **When** embedding is requested, **Then** a clear error is raised (not silent fallback)

---

### User Story 2 - Ollama Embedding Adapter (Priority: P1)

As a developer, I want an OllamaEmbeddingAdapter that implements EmbeddingGeneratorPort so that Ollama-hosted models can generate embeddings through the same interface.

**Why this priority**: Required implementation for US1 to work.

**Independent Test**: Instantiate OllamaEmbeddingAdapter, call `embed_text("test")`, verify it returns an Embedding with correct dimensions from the Ollama API.

**Acceptance Scenarios**:

1. **Given** OllamaEmbeddingAdapter configured with `nomic-embed-text`, **When** `embed_text("hello world")` is called, **Then** it returns an Embedding with 768-dimension vector
2. **Given** OllamaEmbeddingAdapter, **When** `embed_batch(["a", "b", "c"])` is called, **Then** it returns 3 Embeddings efficiently (batched API calls)
3. **Given** OllamaEmbeddingAdapter, **When** `dimensions` property is accessed, **Then** it returns the correct dimension count for the configured model
4. **Given** OllamaEmbeddingAdapter, **When** Ollama returns an error, **Then** adapter raises a descriptive exception (not raw HTTP error)

---

### User Story 3 - Re-indexing Workflow for Model Changes (Priority: P2)

As a memoria operator, I want a safe re-indexing workflow when switching embedding models so that the vector store is consistent with the active model.

**Why this priority**: Without this, switching models produces a broken index (old embeddings incompatible with new model's query embeddings).

**Independent Test**: Switch from `all-MiniLM-L6-v2` to `nomic-embed-text`, run re-index, verify all chunks have new-dimension embeddings and search works correctly.

**Acceptance Scenarios**:

1. **Given** an index built with model A, **When** config changes to model B and re-index is triggered, **Then** the old collection is dropped and rebuilt with model B embeddings
2. **Given** a re-index in progress, **When** the process is interrupted, **Then** no partial/corrupt index remains (atomic swap or clear error state)
3. **Given** model B requires different dimensions than model A, **When** re-indexing completes, **Then** ChromaDB collection metadata reflects new dimensions

---

### User Story 4 - Embedding Model Benchmarking (Priority: P2)

As a memoria developer, I want to benchmark different embedding models against the same query set to find the model that produces the best confidence score distribution.

**Why this priority**: This is the end goal - finding a model that fixes SC-002.

**Independent Test**: Run benchmark script with 3 models, get a comparison table showing score ranges, latencies, and quality metrics per model.

**Acceptance Scenarios**:

1. **Given** a benchmark script and list of models, **When** benchmark runs, **Then** it produces per-model metrics: mean score, score range, P50/P99 latency, dimension count
2. **Given** benchmark results, **When** compared side by side, **Then** score range differences are visible (target: find model with range > 0.3)
3. **Given** a corpus of 18K chunks, **When** benchmarking a model, **Then** full re-index + 20 query benchmark completes (not just single-query test)

---

### Edge Cases

- What happens when Ollama model is not pulled yet? (Should provide clear error with `ollama pull <model>` instructions)
- What happens when embedding dimensions change between models? (ChromaDB collection must be recreated)
- What happens when relishhost2 is offline? (Clear error, not silent degradation)
- What happens with very large batch sizes to Ollama API? (Need to respect Ollama's batch limits)
- What happens if model produces different dimensions than expected? (Validate at startup)

## Requirements

### Functional Requirements

- **FR-001**: System MUST support configuring embedding backend via `MEMORIA_EMBEDDING_BACKEND` env var (values: `sentence_transformers`, `ollama`)
- **FR-002**: System MUST support configuring embedding model via `MEMORIA_EMBEDDING_MODEL` env var
- **FR-003**: System MUST default to `sentence_transformers` backend with `all-MiniLM-L6-v2` when no env vars are set (backward compatibility)
- **FR-004**: OllamaEmbeddingAdapter MUST implement `EmbeddingGeneratorPort` protocol (embed_text, embed_batch, dimensions, model_name)
- **FR-005**: OllamaEmbeddingAdapter MUST connect to Ollama via HTTP API at configurable host/port (default: 192.168.1.171:11434)
- **FR-006**: System MUST detect dimension mismatch between configured model and existing ChromaDB collection
- **FR-007**: System MUST provide a re-indexing command/workflow that atomically rebuilds the collection with new embeddings
- **FR-008**: System MUST NOT break existing `search_knowledge()` or `index_documents()` API signatures

### Key Entities

- **EmbeddingConfig**: Value object holding backend type, model name, host, port, timeout settings
- **OllamaEmbeddingAdapter**: New adapter implementing EmbeddingGeneratorPort via Ollama HTTP API

### Candidate Embedding Models to Test

| Model | Dimensions | Size | Notes |
|-------|-----------|------|-------|
| all-MiniLM-L6-v2 | 384 | 80MB | Current (baseline) |
| nomic-embed-text | 768 | 274MB | Good quality, Ollama native |
| mxbai-embed-large | 1024 | 670MB | High quality, larger |
| snowflake-arctic-embed:m | 768 | 436MB | Strong benchmark performer |
| bge-large-en-v1.5 | 1024 | 1.3GB | Top MTEB scores |

All models fit comfortably within RTX 5060 Ti 16GB VRAM.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Embedding backend is configurable via env vars with zero code changes to consumers
- **SC-002**: At least one Ollama model produces confidence score range > 0.3 on the 18K chunk corpus (fixing spec 002 SC-002)
- **SC-003**: OllamaEmbeddingAdapter passes all EmbeddingGeneratorPort conformance tests
- **SC-004**: Re-indexing 18K chunks with new model completes without errors
- **SC-005**: Search latency with Ollama embeddings < 3s P99 (network hop to relishhost2 adds latency)
- **SC-006**: Zero breaking changes to existing API (search_knowledge, index_documents signatures unchanged)

## Technical Notes

### macOS Network Restriction

Python HTTP libraries (requests, httpx) may be blocked by macOS network security when called from Claude Code's Python interpreter. The existing `ollama_http_client.py` in localAgent solves this with a subprocess curl wrapper. The new adapter should reuse this pattern or the ollamaLocal client.

### Ollama Embedding API

```bash
# Ollama embedding endpoint
curl http://192.168.1.171:11434/api/embed -d '{
  "model": "nomic-embed-text",
  "input": ["text to embed"]
}'
# Returns: {"embeddings": [[0.1, 0.2, ...]]}
```

### Architecture Fit

The clean architecture already supports this via the port/adapter pattern:
- `EmbeddingGeneratorPort` (protocol) - no changes needed
- `SentenceTransformerAdapter` - no changes needed (remains default)
- `OllamaEmbeddingAdapter` - NEW adapter, same port
- Factory/config logic in `skill_helpers.py` to select adapter based on env vars
