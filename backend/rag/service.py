"""RAG Ingestion and Semantic Retrieval Service (Phase 3 - Deliverable D-10)."""

import uuid
from typing import Any, Dict, List, Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.rag.chunking import chunk_document
from backend.rag.embeddings import compute_cosine_similarity, get_embedding_provider
from backend.rag.schemas import (
    DocumentIngestRequest,
    KnowledgeCitation,
    RetrievalRequest,
    RetrievalResponse,
)
from database.models.enums import DocumentStatus, DocumentType
from database.models.knowledge import KnowledgeChunk, KnowledgeDocument


class RAGService:
    """Service layer orchestrating knowledge document ingestion, chunking,

    embedding generation, and semantic retrieval with citation provenance.
    """

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db
        self.embedding_provider = get_embedding_provider()

    def _resolve_db(self, db: Optional[Session]) -> Session:
        session = db or self.db
        if not session:
            raise ValueError("Database session must be provided to RAGService.")
        return session

    def ingest_document(
        self,
        request_or_db: Optional[Any] = None,
        title: Optional[str] = None,
        document_type: Optional[DocumentType] = None,
        source: Optional[str] = None,
        content: Optional[str] = None,
        version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None,
        doc_type: Optional[DocumentType] = None,
        document_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> KnowledgeDocument:
        """Ingests a knowledge document, chunks it deterministically, generates embeddings,

        and atomically persists documents and chunks. Re-ingestion replaces existing chunks
        for that version to avoid duplicate retrieval artifacts.
        """
        req: Optional[DocumentIngestRequest] = None
        session: Optional[Session] = db

        if isinstance(request_or_db, DocumentIngestRequest):
            req = request_or_db
        elif isinstance(request_or_db, Session):
            session = request_or_db

        if req:
            title = req.title
            doc_type_val = req.document_type or req.doc_type or DocumentType.POLICY
            source = req.source
            content = req.content
            version = req.version
            metadata = req.metadata
            document_id = req.document_id
        else:
            doc_type_val = document_type or doc_type or DocumentType.POLICY
            if not title or not source or not content:
                raise ValueError("title, source, and content are required for document ingestion.")

        active_db = self._resolve_db(session)
        doc_meta = dict(metadata or {})
        if document_id:
            doc_meta["document_id"] = document_id
            doc_meta["policy_id"] = document_id

        # 1. Check for existing document with same source or title
        existing_doc = active_db.scalar(
            select(KnowledgeDocument).where(
                (KnowledgeDocument.source == source) | (KnowledgeDocument.title == title)
            )
        )

        if existing_doc:
            doc = existing_doc
            doc.title = title
            doc.document_type = doc_type_val
            doc.source = source
            doc.version = version
            doc.content = content
            doc.doc_metadata = doc_meta
            doc.status = DocumentStatus.ACTIVE
            # Delete existing chunks for this document
            for old_chunk in list(doc.chunks):
                active_db.delete(old_chunk)
            active_db.flush()
        else:
            doc = KnowledgeDocument(
                id=uuid.uuid4(),
                title=title,
                document_type=doc_type_val,
                source=source,
                version=version,
                status=DocumentStatus.ACTIVE,
                content=content,
                doc_metadata=doc_meta,
            )
            active_db.add(doc)
            active_db.flush()

        # 2. Chunk document deterministically
        raw_chunks = chunk_document(content)
        if raw_chunks:
            texts = [c["chunk_text"] for c in raw_chunks]
            embeddings = self.embedding_provider.embed_batch(texts)

            for chunk_data, emb in zip(raw_chunks, embeddings):
                chunk_obj = KnowledgeChunk(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    chunk_text=chunk_data["chunk_text"],
                    chunk_index=chunk_data["chunk_index"],
                    document_version=version,
                    embedding=emb,
                    chunk_metadata=chunk_data.get("metadata", {}),
                )
                active_db.add(chunk_obj)

        active_db.commit()
        active_db.refresh(doc)
        return doc

    def get_document(
        self,
        document_id: Any,
        db: Optional[Session] = None,
    ) -> Optional[KnowledgeDocument]:
        """Retrieves a knowledge document by UUID, title, source, or metadata document_id."""
        active_db = self._resolve_db(db)

        if isinstance(document_id, uuid.UUID):
            return active_db.get(KnowledgeDocument, document_id)

        doc_str = str(document_id)
        # Try finding by UUID parse
        try:
            parsed_uuid = uuid.UUID(doc_str)
            found = active_db.get(KnowledgeDocument, parsed_uuid)
            if found:
                return found
        except ValueError:
            pass

        # Search across all documents
        all_docs = active_db.scalars(select(KnowledgeDocument)).all()
        for d in all_docs:
            if d.document_id == doc_str or d.title.startswith(doc_str) or doc_str in d.source:
                return d

        return None

    def list_documents(
        self,
        status: Optional[DocumentStatus] = None,
        doc_type: Optional[DocumentType] = None,
        document_type: Optional[DocumentType] = None,
        limit: int = 50,
        offset: int = 0,
        db: Optional[Session] = None,
    ) -> Sequence[KnowledgeDocument]:
        """Lists knowledge documents with optional status/type filtering."""
        active_db = self._resolve_db(db)
        query = select(KnowledgeDocument)
        target_type = doc_type or document_type
        if status:
            query = query.where(KnowledgeDocument.status == status)
        if target_type:
            query = query.where(KnowledgeDocument.document_type == target_type)
        query = query.order_by(KnowledgeDocument.created_at.desc()).limit(limit).offset(offset)
        return active_db.scalars(query).all()

    def retrieve(
        self,
        request_or_query: Any = None,
        query: Optional[str] = None,
        top_k: int = 3,
        document_type: Optional[DocumentType] = None,
        doc_types: Optional[List[DocumentType]] = None,
        min_score: float = 0.0,
        min_similarity: Optional[float] = None,
        db: Optional[Session] = None,
    ) -> RetrievalResponse:
        """Performs semantic cosine retrieval against active knowledge chunks.

        Returns RetrievalResponse complete with provenance metadata and citations.
        """
        active_db = self._resolve_db(db)

        search_query: str = ""
        target_k = top_k
        target_doc_types = doc_types or ([document_type] if document_type else None)
        threshold = min_similarity if min_similarity is not None else min_score

        if isinstance(request_or_query, RetrievalRequest):
            search_query = request_or_query.query
            target_k = request_or_query.top_k
            if request_or_query.doc_types:
                target_doc_types = request_or_query.doc_types
            elif request_or_query.document_type:
                target_doc_types = [request_or_query.document_type]
            threshold = request_or_query.min_score
        elif isinstance(request_or_query, str):
            search_query = request_or_query
        elif query:
            search_query = query

        if not search_query:
            return RetrievalResponse(query="", citations=[], total_matches=0)

        query_emb = self.embedding_provider.embed_text(search_query)

        # Query all active chunks
        stmt = (
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.status == DocumentStatus.ACTIVE)
        )
        if target_doc_types:
            stmt = stmt.where(KnowledgeDocument.document_type.in_(target_doc_types))

        results = active_db.execute(stmt).all()
        if not results:
            return RetrievalResponse(query=search_query, citations=[], total_matches=0)

        scored_citations: List[KnowledgeCitation] = []
        for chunk, doc in results:
            if not chunk.embedding:
                score = 0.0
            else:
                score = compute_cosine_similarity(query_emb, chunk.embedding)

            if score >= threshold:
                scored_citations.append(
                    KnowledgeCitation(
                        document_id=doc.document_id,
                        title=doc.title,
                        document_type=doc.document_type.value,
                        version=doc.version,
                        chunk_id=str(chunk.id),
                        chunk_index=chunk.chunk_index,
                        source=doc.source,
                        snippet=chunk.chunk_text,
                        text=chunk.chunk_text,
                        score=round(score, 4),
                        similarity_score=round(score, 4),
                        metadata=chunk.chunk_metadata,
                    )
                )

        # Rank by score descending
        scored_citations.sort(key=lambda c: c.score, reverse=True)
        top_hits = scored_citations[:target_k]

        return RetrievalResponse(
            query=search_query,
            citations=top_hits,
            results=top_hits,
            total_matches=len(scored_citations),
            total_count=len(scored_citations),
        )


# Global singleton service instance
rag_service = RAGService()
