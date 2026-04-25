"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # pgvector extension — must exist before any vector columns
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_tiers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tier", sa.String(10), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("knowledge_tiers.id"), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("NOW()"), nullable=False),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tier_id", sa.Integer(), sa.ForeignKey("knowledge_tiers.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("doc_type", sa.String(100), nullable=True),
        sa.Column("data_category", sa.String(50), server_default="compliance", nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("original_filename", sa.String(500), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("ocr_processed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column(
            "superseded_by_id",
            sa.Integer(),
            sa.ForeignKey("documents.id"),
            nullable=True,
        ),
        sa.Column("version_note", sa.String(500), nullable=True),
        sa.Column("pii_notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.text("NOW()"), nullable=False),
    )

    # Partial index — fast "current documents only" queries
    op.create_index(
        "idx_documents_current",
        "documents",
        ["tier_id", "doc_type"],
        postgresql_where=sa.text("superseded_by_id IS NULL"),
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_ref", sa.String(255), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("NOW()"), nullable=False),
    )

    # chunk_embeddings uses vector(768) — must be created via raw DDL
    op.execute("""
        CREATE TABLE chunk_embeddings (
            id           SERIAL PRIMARY KEY,
            chunk_id     INTEGER NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
            embedding    vector(768) NOT NULL,
            model_name   VARCHAR(100) NOT NULL DEFAULT 'nomic-embed-text',
            model_version VARCHAR(50) NOT NULL,
            created_at   TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # HNSW index for cosine similarity — performs correctly at any dataset size.
    # Do NOT use ivfflat; it is ignored by the query planner on small tables.
    op.execute("""
        CREATE INDEX ON chunk_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    op.create_table(
        "query_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("tier_id", sa.Integer(), sa.ForeignKey("knowledge_tiers.id"), nullable=True),
        sa.Column("query_source", sa.String(20), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("retrieved_chunks", postgresql.JSONB(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("pii_redacted", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.text("NOW()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("query_log")
    op.execute("DROP TABLE IF EXISTS chunk_embeddings")
    op.drop_table("document_chunks")
    op.drop_index("idx_documents_current", table_name="documents")
    op.drop_table("documents")
    op.drop_table("knowledge_tiers")
    op.execute("DROP EXTENSION IF EXISTS vector")
