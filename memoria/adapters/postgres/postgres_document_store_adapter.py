"""
PostgresDocumentStoreAdapter - Postgres implementation of DocumentStorePort.

Stores full document content in the `memoria_documents` table.
Connection parameters read from MEMORIA_PG_* environment variables.
Schema is created idempotently on first use.
"""

import hashlib
import os
from datetime import datetime
from typing import Iterator

import psycopg2
import psycopg2.extras

from memoria.domain.entities import StoredDocument


class PostgresDocumentStoreAdapter:
    """
    Postgres-backed document store.

    Implements DocumentStorePort against the `memoria` database on relishhost1.
    Uses psycopg2-binary for synchronous access (matches existing skill_helpers.py pattern).
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self._host = host or os.getenv("MEMORIA_PG_HOST")
        self._port = port or int(os.getenv("MEMORIA_PG_PORT", "0") or "0")
        self._database = database or os.getenv("MEMORIA_PG_DATABASE")
        self._user = user or os.getenv("MEMORIA_PG_USER")
        self._password = password or os.getenv("MEMORIA_PG_PASSWORD", "")
        if not self._host or not self._port or not self._database or not self._user:
            raise RuntimeError(
                "MEMORIA_PG_HOST, MEMORIA_PG_PORT, MEMORIA_PG_DATABASE, and MEMORIA_PG_USER must be set. "
                "Run: bash install-plugin.sh (from memoria plugin dir) to configure ~/.claude/memoria.env"
            )
        self._schema_ensured = False

    def _connect(self) -> psycopg2.extensions.connection:
        return psycopg2.connect(
            host=self._host,
            port=self._port,
            dbname=self._database,
            user=self._user,
            password=self._password,
        )

    def _ensure_schema(self) -> None:
        """Create memoria_documents table and indexes idempotently."""
        if self._schema_ensured:
            return
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS memoria_documents (
                        id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                        source_id    TEXT        NOT NULL UNIQUE,
                        title        TEXT        NOT NULL,
                        content      TEXT        NOT NULL,
                        fingerprint  TEXT        NOT NULL,
                        version      INTEGER     NOT NULL DEFAULT 1,
                        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        active       BOOLEAN     NOT NULL DEFAULT TRUE
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_memoria_docs_source
                    ON memoria_documents (source_id) WHERE active = TRUE
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_memoria_docs_fingerprint
                    ON memoria_documents (fingerprint) WHERE active = TRUE
                """)
            conn.commit()
        self._schema_ensured = True

    @staticmethod
    def _compute_fingerprint(content: str) -> str:
        """Compute SHA-256 hex fingerprint of normalized content."""
        return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_document(row: dict) -> StoredDocument:
        return StoredDocument(
            id=str(row["id"]),
            source_id=row["source_id"],
            title=row["title"],
            content=row.get("content", ""),
            fingerprint=row["fingerprint"],
            version=row["version"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def store(self, source_id: str, title: str, content: str) -> StoredDocument:
        """Upsert document. No-op if fingerprint unchanged; increments version if changed."""
        self._ensure_schema()
        fingerprint = self._compute_fingerprint(content)

        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Check for any existing row (active or soft-deleted)
                cur.execute(
                    "SELECT id, fingerprint, version, created_at, active "
                    "FROM memoria_documents WHERE source_id = %s",
                    (source_id,),
                )
                existing = cur.fetchone()

                if existing and existing["active"]:
                    if existing["fingerprint"] == fingerprint:
                        # No change — return current record without writing
                        cur.execute(
                            "SELECT * FROM memoria_documents WHERE source_id = %s AND active = TRUE",
                            (source_id,),
                        )
                        return self._row_to_document(cur.fetchone())

                    # Content changed — update
                    cur.execute(
                        """
                        UPDATE memoria_documents
                        SET title = %s, content = %s, fingerprint = %s,
                            version = version + 1, updated_at = NOW()
                        WHERE source_id = %s AND active = TRUE
                        RETURNING *
                        """,
                        (title, content, fingerprint, source_id),
                    )
                    row = cur.fetchone()
                elif existing and not existing["active"]:
                    # Previously soft-deleted — reactivate and update
                    cur.execute(
                        """
                        UPDATE memoria_documents
                        SET title = %s, content = %s, fingerprint = %s,
                            version = %s, active = TRUE, updated_at = NOW()
                        WHERE source_id = %s
                        RETURNING *
                        """,
                        (title, content, fingerprint, existing["version"] + 1, source_id),
                    )
                    row = cur.fetchone()
                else:
                    # New document — insert
                    cur.execute(
                        """
                        INSERT INTO memoria_documents (source_id, title, content, fingerprint)
                        VALUES (%s, %s, %s, %s)
                        RETURNING *
                        """,
                        (source_id, title, content, fingerprint),
                    )
                    row = cur.fetchone()

            conn.commit()
        return self._row_to_document(row)

    def get(self, source_id: str) -> StoredDocument | None:
        """Retrieve full document by source_id."""
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM memoria_documents WHERE source_id = %s AND active = TRUE",
                    (source_id,),
                )
                row = cur.fetchone()
        return self._row_to_document(row) if row else None

    def list_all(self) -> list[StoredDocument]:
        """Return all active documents (content included)."""
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM memoria_documents WHERE active = TRUE ORDER BY source_id"
                )
                rows = cur.fetchall()
        return [self._row_to_document(r) for r in rows]

    def delete(self, source_id: str) -> bool:
        """Soft-delete document. Returns True if deleted, False if not found."""
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE memoria_documents SET active = FALSE, updated_at = NOW() "
                    "WHERE source_id = %s AND active = TRUE",
                    (source_id,),
                )
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    def get_fingerprint(self, source_id: str) -> str | None:
        """Return fingerprint only — fast change detection path."""
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT fingerprint FROM memoria_documents "
                    "WHERE source_id = %s AND active = TRUE",
                    (source_id,),
                )
                row = cur.fetchone()
        return row[0] if row else None

    def export_all(self) -> Iterator[StoredDocument]:
        """Stream all active documents with full content."""
        self._ensure_schema()
        conn = self._connect()
        try:
            with conn.cursor(
                name="export_cursor", cursor_factory=psycopg2.extras.RealDictCursor
            ) as cur:
                cur.execute(
                    "SELECT * FROM memoria_documents WHERE active = TRUE ORDER BY source_id"
                )
                for row in cur:
                    yield self._row_to_document(row)
        finally:
            conn.close()

    def count(self) -> int:
        """Return count of active documents."""
        self._ensure_schema()
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM memoria_documents WHERE active = TRUE")
                return cur.fetchone()[0]

    def health_check(self) -> bool:
        """Return True if Postgres is reachable."""
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception:
            return False
