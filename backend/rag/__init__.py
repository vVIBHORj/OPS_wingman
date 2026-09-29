"""
RAG System package for OpsWingman.
"""

from backend.rag.schemas import (
    KnowledgeCitation,
    DocumentIngestRequest,
    DocumentResponse,
    RetrievalRequest,
    RetrievalResponse,
)
from backend.rag.embeddings import BaseEmbeddingProvider, DeterministicLocalEmbeddingProvider, get_embedding_provider
from backend.rag.chunking import chunk_document
from backend.rag.service import RAGService, rag_service
from backend.rag.seed_knowledge import seed_knowledge_documents

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
