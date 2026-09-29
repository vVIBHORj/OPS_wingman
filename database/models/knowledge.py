"""Knowledge Document and Chunk database models for OpsWingman RAG System (Phase 3 - Deliverable D-10)."""

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import Enum as SQLEnum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, GUID, TimestampMixin, UUIDPrimaryKeyMixin
from database.models.enums import DocumentStatus, DocumentType


class KnowledgeDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Represents an ingested operational knowledge document (Policy, SOP, FAQ).

    Tracks versioning and publishing status.
    """

    __tablename__ = "knowledge_documents"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType, native_enum=False, length=50),
        default=DocumentType.POLICY,
        index=True,
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        SQLEnum(DocumentStatus, native_enum=False, length=50),
        default=DocumentStatus.ACTIVE,
        index=True,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    doc_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    chunks: Mapped[List["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="KnowledgeChunk.chunk_index",
    )

    __table_args__ = (
        Index("ix_knowledge_documents_source_version", "source", "version"),
    )

    @property
    def document_id(self) -> str:
        if self.doc_metadata and isinstance(self.doc_metadata, dict):
            if "policy_id" in self.doc_metadata:
                return str(self.doc_metadata["policy_id"])
            if "sop_id" in self.doc_metadata:
                return str(self.doc_metadata["sop_id"])
        if ":" in self.title:
            return self.title.split(":")[0].strip()
        return str(self.id)

    @property
    def doc_type(self) -> DocumentType:
        return self.document_type

    def __repr__(self) -> str:
        return f"<KnowledgeDocument(id={self.id}, title='{self.title}', type='{self.document_type.value}', v='{self.version}')>"


class KnowledgeChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Deterministic chunk of a KnowledgeDocument for semantic retrieval and citation provenance."""

    __tablename__ = "knowledge_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    document_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(JSON, nullable=True)
    chunk_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    document: Mapped["KnowledgeDocument"] = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        Index("ix_knowledge_chunks_doc_idx", "document_id", "chunk_index"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeChunk(id={self.id}, doc_id={self.document_id}, idx={self.chunk_index})>"
