"""Unit tests for Phase 3 D-10 RAG Knowledge Base."""

import pytest
from sqlalchemy.orm import Session

from backend.rag.chunking import chunk_document
from backend.rag.embeddings import DeterministicLocalEmbeddingProvider
from backend.rag.schemas import DocumentIngestRequest, RetrievalRequest
from backend.rag.seed_knowledge import seed_default_knowledge
from backend.rag.service import RAGService
from database.models.enums import DocumentStatus, DocumentType


def test_chunking_deterministic():
    content = """# Section 1
This is the introduction to order processing.
Orders can be cancelled before dispatch.

# Section 2
Refunds are processed within 5-7 business days for eligible returns.
"""
    chunks = chunk_document(content, max_chunk_size=100)
    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert "Section 1" in chunks[0].text or "Section 2" in chunks[1].text


def test_embedding_provider_deterministic():
    provider = DeterministicLocalEmbeddingProvider(dim=384)
    emb1 = provider.embed_text("cancellation policy before shipment")
    emb2 = provider.embed_text("cancellation policy before shipment")
    emb_diff = provider.embed_text("warehouse dispatch logistics truck")

    assert len(emb1) == 384
    assert emb1 == emb2  # 100% deterministic

    # Similarity with identical text is 1.0
    sim_self = provider.similarity(emb1, emb2)
    assert pytest.approx(sim_self, 0.001) == 1.0

    # Similarity with different text is lower
    sim_diff = provider.similarity(emb1, emb_diff)
    assert sim_diff < 1.0


def test_document_ingestion_and_retrieval(db_session: Session):
    service = RAGService(db_session)
    req = DocumentIngestRequest(
        document_id="POL-TEST-001",
        title="Test Cancellation Policy",
        doc_type=DocumentType.POLICY,
        source="internal://legal/test_cancel.md",
        version="1.0.0",
        content="Orders in PENDING or CONFIRMED state may be cancelled directly before dispatch.",
        metadata={"department": "operations", "tag": "cancellation"},
    )
    doc = service.ingest_document(req)
    assert doc.document_id == "POL-TEST-001"
    assert doc.title == "Test Cancellation Policy"
    assert doc.version == "1.0.0"
    assert len(doc.chunks) >= 1

    # Retrieve
    retrieval_res = service.retrieve(
        RetrievalRequest(query="cancel order before dispatch", top_k=3)
    )
    assert len(retrieval_res.results) > 0
    top_hit = retrieval_res.results[0]
    assert top_hit.document_id == "POL-TEST-001"
    assert top_hit.version == "1.0.0"
    assert "cancelled directly" in top_hit.text
    assert top_hit.similarity_score > 0.0


def test_document_reingestion_updates_cleanly(db_session: Session):
    service = RAGService(db_session)
    req1 = DocumentIngestRequest(
        document_id="POL-UPDATE-001",
        title="Initial Policy",
        doc_type=DocumentType.POLICY,
        source="internal://legal/policy.md",
        version="1.0.0",
        content="Original content version 1",
    )
    service.ingest_document(req1)
    doc1 = service.get_document("POL-UPDATE-001")
    assert doc1 is not None
    assert doc1.version == "1.0.0"
    assert len(doc1.chunks) == 1

    # Re-ingest with version 1.1.0
    req2 = DocumentIngestRequest(
        document_id="POL-UPDATE-001",
        title="Updated Policy Title",
        doc_type=DocumentType.POLICY,
        source="internal://legal/policy.md",
        version="1.1.0",
        content="Updated content version 2 with more detailed rules",
    )
    service.ingest_document(req2)
    doc2 = service.get_document("POL-UPDATE-001")
    assert doc2 is not None
    assert doc2.version == "1.1.0"
    assert doc2.title == "Updated Policy Title"
    # Old chunks replaced without orphaned duplicate records
    assert len(doc2.chunks) == 1
    assert "Updated content" in doc2.chunks[0].chunk_text


def test_metadata_filtering(db_session: Session):
    service = RAGService(db_session)
    service.ingest_document(
        DocumentIngestRequest(
            document_id="SOP-FIN-001",
            title="Finance SOP",
            doc_type=DocumentType.SOP,
            source="internal://sop/fin.md",
            version="1.0.0",
            content="Bank reconciliation and UPI refund SOP",
        )
    )
    service.ingest_document(
        DocumentIngestRequest(
            document_id="FAQ-CUST-001",
            title="Customer FAQ",
            doc_type=DocumentType.FAQ,
            source="internal://faq/cust.md",
            version="1.0.0",
            content="General questions about return windows",
        )
    )

    # Filter by SOP
    sop_docs = service.list_documents(doc_type=DocumentType.SOP)
    assert any(d.document_id == "SOP-FIN-001" for d in sop_docs)
    assert not any(d.document_id == "FAQ-CUST-001" for d in sop_docs)

    # Filter retrieval by doc_type
    res_sop = service.retrieve(
        RetrievalRequest(query="return window", doc_types=[DocumentType.FAQ])
    )
    assert all(r.document_id.startswith("FAQ") for r in res_sop.results)


def test_seed_default_knowledge(db_session: Session):
    count = seed_default_knowledge(db_session)
    assert count >= 5
    service = RAGService(db_session)
    shp_doc = service.get_document("POL-SHP-001")
    can_doc = service.get_document("POL-CAN-001")
    ref_doc = service.get_document("POL-REF-001")

    assert shp_doc is not None
    assert can_doc is not None
    assert ref_doc is not None
