# Data Model: Memoria Performance Optimization

**Feature**: 002-memoria-performance
**Date**: 2026-01-31

## Overview

This document defines the entities and data structures for performance monitoring and batch operations in memoria.

## Performance Metrics

### PerformanceMetrics
**Purpose**: Track search and indexing performance

**Attributes**:
- `operation_type`: string ("search" | "indexing")
- `start_time`: datetime
- `end_time`: datetime
- `duration_ms`: float
- `document_count`: int (for indexing) or result_count (for search)
- `memory_usage_mb`: float (peak memory during operation)
- `success`: boolean

**Relationships**: None (metrics are independent observations)

## Batch Processing

### BatchEmbeddingRequest
**Purpose**: Request object for batch embedding generation

**Attributes**:
- `texts`: list[string] (texts to embed, max 500 per batch)
- `batch_size`: int (internal batching within request, default 32)
- `show_progress`: boolean (display progress bar)

**Validation Rules**:
- texts list must not be empty
- each text must be <10,000 characters
- batch_size must be between 1 and 500

### BatchEmbeddingResponse
**Purpose**: Response from batch embedding operation

**Attributes**:
- `embeddings`: list[list[float]] (384-dim vectors for all-MiniLM-L6-v2)
- `failed_indices`: list[int] (indices of texts that failed)
- `processing_time_ms`: float

## Progress Tracking

### ProgressTracker
**Purpose**: Track progress of long-running indexing operations

**Attributes**:
- `total_documents`: int
- `processed_documents`: int
- `failed_documents`: int
- `current_document`: string (filename)
- `start_time`: datetime
- `estimated_completion`: datetime (calculated)

**State Transitions**:
- PENDING → IN_PROGRESS (when indexing starts)
- IN_PROGRESS → COMPLETED (when all docs processed)
- IN_PROGRESS → FAILED (on critical error)

## Search Result Enhancement

### DetailedSearchResult
**Purpose**: Extended search result with performance metadata

**Attributes**:
- All attributes from existing SearchResult entity
- `retrieval_time_ms`: float (time to retrieve this result)
- `rerank_score`: float (if reranking applied)
- `chunk_id`: string (which chunk matched)

## Architecture Notes

**Clean Architecture Compliance**:
- All entities are immutable (frozen dataclasses)
- No dependencies on adapters or external libraries
- Pure data structures with validation rules only

**Existing Entities** (no changes):
- Document (domain/entities.py)
- SearchResult (domain/entities.py)
- Embedding (domain/entities.py)
