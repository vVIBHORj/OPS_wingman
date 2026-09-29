"""Replaceable Embedding Provider Interface and Deterministic Local Embeddings (Phase 3 - Deliverable D-10)."""

import math
import hashlib
import re
from abc import ABC, abstractmethod
from typing import List, Optional


class BaseEmbeddingProvider(ABC):
    """Abstract contract for text embedding generation.

    Enables pluggable embedding backends (Local, OpenAI, SentenceTransformers, etc.).
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector embedding dimensionality."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generates a dense vector embedding for a single text string."""
        pass

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generates vector embeddings for a batch of text strings."""
        return [self.embed_text(t) for t in texts]

    def similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Calculates cosine similarity between two vector embeddings."""
        return compute_cosine_similarity(vec_a, vec_b)


class DeterministicLocalEmbeddingProvider(BaseEmbeddingProvider):
    """Local, deterministic semantic embedding provider.

    Uses multi-scale token, n-gram hashing, and cosine normalization across 384 dimensions.
    Operates 100% offline with zero external network or vendor dependencies.
    """

    def __init__(self, dimension: int = 384, dim: Optional[int] = None) -> None:
        self._dim = dim if dim is not None else dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> List[float]:
        """Transforms text into a normalized dense vector using token hashing and sub-word n-grams."""
        vec = [0.0] * self._dim
        cleaned = text.lower().strip()
        if not cleaned:
            return vec

        tokens = re.findall(r"\b\w+\b", cleaned)
        if not tokens:
            return vec

        # 1. Full Token Feature Hashing
        for i, token in enumerate(tokens):
            weight = 1.0 / (1.0 + math.log(1 + i))
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if ((h >> 4) & 1) == 0 else -1.0
            vec[idx] += sign * weight * 2.0

            # 2. Sub-word character trigrams for morphological similarity
            if len(token) >= 3:
                for j in range(len(token) - 2):
                    trigram = token[j:j+3]
                    th = int(hashlib.sha256(trigram.encode("utf-8")).hexdigest(), 16)
                    tidx = th % self._dim
                    tsign = 1.0 if ((th >> 3) & 1) == 0 else -1.0
                    vec[tidx] += tsign * (weight * 0.5)

        # 3. L2 Normalization (Unit Vector) for exact Cosine Similarity via Dot Product
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            return [float(x / norm) for x in vec]
        return vec


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two normalized vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    return float(max(-1.0, min(1.0, dot)))


# Global default embedding provider instance
_default_provider: BaseEmbeddingProvider = DeterministicLocalEmbeddingProvider()


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Returns the configured embedding provider."""
    return _default_provider
