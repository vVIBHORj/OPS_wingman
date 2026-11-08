"""
RAG System package for OpsWingman.
"""

from backend.rag.chunking import chunk_document
from backend.rag.embeddings import (
    BaseEmbeddingProvider,
    DeterministicLocalEmbeddingProvider,
    get_embedding_provider,
)
from backend.rag.schemas import (
    DocumentIngestRequest,
    DocumentResponse,
    KnowledgeCitation,
    RetrievalRequest,
    RetrievalResponse,
)
from backend.rag.seed_knowledge import seed_knowledge_documents
from backend.rag.service import RAGService, rag_service

__all__ = [
    "KnowledgeCitation",
    "DocumentIngestRequest",
    "DocumentResponse",
    "RetrievalRequest",
    "RetrievalResponse",
    "BaseEmbeddingProvider",
    "DeterministicLocalEmbeddingProvider",
    "get_embedding_provider",
    "chunk_document",
    "RAGService",
    "rag_service",
    "seed_knowledge_documents",
]
