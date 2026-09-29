"""Pydantic Schemas for Knowledge Ingestion, Retrieval, and Citations (Phase 3 - Deliverable D-10)."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from database.models.enums import DocumentStatus, DocumentType


class KnowledgeCitation(BaseModel):
    """Standardized citation provenance container attaching ground-truth knowledge snippets to decisions."""
    document_id: str = Field(..., description="UUID or identifier of source knowledge document")
    title: str = Field(..., description="Document title / policy name")
    document_type: str = Field(default="POLICY", description="POLICY, SOP, FAQ, GUIDELINE")
    version: str = Field(default="1.0.0", description="Document version string, e.g. 1.0.0")
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="UUID of specific chunk")
    chunk_index: int = Field(default=0, description="0-indexed sequence of chunk in document")
    source: str = Field(default="", description="Document source identifier")
    snippet: str = Field(default="", description="Exact textual excerpt from the chunk")
    text: str = Field(default="", description="Alias for snippet")
    score: float = Field(default=1.0, description="Relevance similarity score (0.0 to 1.0)")
    similarity_score: float = Field(default=1.0, description="Alias for score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional contextual metadata")

    def __init__(self, **data: Any) -> None:
        if "text" in data and not data.get("snippet"):
            data["snippet"] = data["text"]
        elif "snippet" in data and not data.get("text"):
            data["text"] = data["snippet"]
        if "similarity_score" in data and "score" not in data:
            data["score"] = float(data["similarity_score"])
        elif "score" in data and "similarity_score" not in data:
            data["similarity_score"] = float(data["score"])
        super().__init__(**data)


class DocumentIngestRequest(BaseModel):
    """Request payload to ingest or update a knowledge document."""
    document_id: Optional[str] = Field(default=None, description="Optional custom document string ID")
    title: str = Field(..., min_length=2, description="Title of knowledge document")
    document_type: DocumentType = Field(default=DocumentType.POLICY, description="Document type classification")
    doc_type: Optional[DocumentType] = Field(default=None, description="Alias for document_type")
    source: str = Field(..., min_length=2, description="Source identifier, e.g. 'policies/cancellation_v1.md'")
    version: str = Field(default="1.0.0", description="Document semantic version")
    content: str = Field(..., min_length=10, description="Raw text or markdown content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary document metadata")

    def __init__(self, **data: Any) -> None:
        if "doc_type" in data and "document_type" not in data:
            data["document_type"] = data["doc_type"]
        elif "document_type" in data and "doc_type" not in data:
            data["doc_type"] = data["document_type"]
        super().__init__(**data)


class KnowledgeChunkResponse(BaseModel):
    """Response model for a knowledge chunk."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    chunk_text: str
    chunk_index: int
    document_version: str
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentResponse(BaseModel):
    """Response model representing an ingested knowledge document."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: Optional[str] = None
    title: str
    document_type: DocumentType
    source: str
    version: str
    status: DocumentStatus
    content: str
    doc_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    chunk_count: Optional[int] = None
    chunks: List[KnowledgeChunkResponse] = []

    def __init__(self, **data: Any) -> None:
        if "doc_metadata" in data and isinstance(data["doc_metadata"], dict):
            if "policy_id" in data["doc_metadata"] and not data.get("document_id"):
                data["document_id"] = data["doc_metadata"]["policy_id"]
            elif "sop_id" in data["doc_metadata"] and not data.get("document_id"):
                data["document_id"] = data["doc_metadata"]["sop_id"]
        if not data.get("document_id") and "title" in data:
            parts = data["title"].split(":")
            if len(parts) > 1 and ("POL-" in parts[0] or "SOP-" in parts[0] or "FAQ-" in parts[0]):
                data["document_id"] = parts[0].strip()
        super().__init__(**data)



class RetrievalRequest(BaseModel):
    """Request payload to query the RAG knowledge store."""
    query: str = Field(..., min_length=1, description="Natural language search query or operational keyword")
    top_k: int = Field(default=3, ge=1, le=20, description="Maximum number of relevant citations to return")
    document_type: Optional[DocumentType] = Field(default=None, description="Optional filter by document type")
    doc_types: Optional[List[DocumentType]] = Field(default=None, description="Optional filter by list of document types")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum relevance threshold")
    min_similarity: Optional[float] = Field(default=None, description="Alias for min_score")

    def __init__(self, **data: Any) -> None:
        if "min_similarity" in data and "min_score" not in data:
            data["min_score"] = float(data["min_similarity"])
        elif "min_score" in data and "min_similarity" not in data:
            data["min_similarity"] = float(data["min_score"])
        super().__init__(**data)


class RetrievalResponse(BaseModel):
    """Response container for semantic knowledge retrieval."""
    query: str
    citations: List[KnowledgeCitation]
    results: List[KnowledgeCitation] = []
    total_matches: int = 0
    total_count: int = 0

    def __init__(self, **data: Any) -> None:
        if "citations" in data and not data.get("results"):
            data["results"] = data["citations"]
        elif "results" in data and not data.get("citations"):
            data["citations"] = data["results"]
        if "total_matches" in data and not data.get("total_count"):
            data["total_count"] = data["total_matches"]
        elif "total_count" in data and not data.get("total_matches"):
            data["total_matches"] = data["total_count"]
        super().__init__(**data)
