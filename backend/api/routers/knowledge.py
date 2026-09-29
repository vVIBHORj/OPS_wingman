"""Knowledge (RAG) API Router for OpsWingman Phase 3 (D-10).

Exposes endpoints for document ingestion, retrieval, and document management.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.rag.schemas import (
    DocumentIngestRequest,
    DocumentResponse,
    RetrievalRequest,
    RetrievalResponse,
)
from backend.rag.service import RAGService
from database.models.enums import DocumentStatus, DocumentType
from database.session import get_db

router = APIRouter(prefix="/knowledge", tags=["Knowledge & RAG"])


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def ingest_document(
    request: DocumentIngestRequest,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Ingest a knowledge document (Policy/SOP/FAQ), chunk, embed, and store deterministically."""
    service = RAGService(db)
    doc = service.ingest_document(request)
    return DocumentResponse.model_validate(doc)


@router.get("/documents", response_model=List[DocumentResponse])
def list_documents(
    doc_type: Optional[DocumentType] = Query(default=None, description="Filter by document type"),
    doc_status: Optional[DocumentStatus] = Query(default=None, description="Filter by status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> List[DocumentResponse]:
    """List ingested knowledge documents."""
    service = RAGService(db)
    docs = service.list_documents(doc_type=doc_type, status=doc_status, limit=limit, offset=offset)
    return [DocumentResponse.model_validate(d) for d in docs]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Get a knowledge document by its unique string identifier (e.g. POL-SHP-001)."""
    service = RAGService(db)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge document '{document_id}' not found.",
        )
    return DocumentResponse.model_validate(doc)


@router.post("/retrieve", response_model=RetrievalResponse)
def retrieve_knowledge(
    request: RetrievalRequest,
    db: Session = Depends(get_db),
) -> RetrievalResponse:
    """Retrieve top-k relevant knowledge chunks with citation provenance and similarity scores."""
    service = RAGService(db)
    return service.retrieve(request)
