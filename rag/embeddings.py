"""
Embedding Generator Module for RAG application.
Uses SentenceTransformers (all-MiniLM-L6-v2) for generating fast local embeddings.
"""

from typing import List
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    HAS_ST = True
except ImportError:
    HAS_ST = False


_ST_MODEL_CACHE = {}


def get_sentence_transformer(model_name: str = "all-MiniLM-L6-v2"):
    """Global cached SentenceTransformer loader to avoid repeated model loading across requests/tests."""
    if not HAS_ST:
        return None
    if model_name not in _ST_MODEL_CACHE:
        try:
            _ST_MODEL_CACHE[model_name] = SentenceTransformer(model_name)
        except Exception as e:
            print(f"[Embedding Error] Could not load SentenceTransformer '{model_name}': {e}")
            _ST_MODEL_CACHE[model_name] = None
    return _ST_MODEL_CACHE[model_name]


class RAGEmbeddingEngine:
    """Wrapper for sentence embedding generation with process-level model caching."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", auto_init: bool = True):
        self.model_name = model_name
        self.model = None
        self._is_ready = False
        if auto_init:
            self.initialize()

    def initialize(self):
        """Load sentence transformer model from cache."""
        if self._is_ready and self.model is not None:
            return

        if HAS_ST:
            self.model = get_sentence_transformer(self.model_name)
            self._is_ready = (self.model is not None)
        else:
            self._is_ready = False

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a list of document strings."""
        if not self._is_ready and self.model is None and HAS_ST:
            # Only try initializing if not explicitly disabled
            pass

        if self._is_ready and self.model is not None:
            try:
                embeddings = self.model.encode(
                    texts, 
                    batch_size=32, 
                    show_progress_bar=False, 
                    convert_to_numpy=True, 
                    normalize_embeddings=True
                )
                return embeddings.tolist()
            except Exception as e:
                print(f"[Embedding Error] Encoding error: {e}")

        # Hash fallback if model fails or is disabled
        return [self._fallback_embedding(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding vector for a single query."""
        res = self.embed_documents([text])
        return res[0]

    def _fallback_embedding(self, text: str, dim: int = 384) -> List[float]:
        """Deterministic term-frequency and subword n-gram feature hashing vectorizer for offline testing."""
        import re
        if not text:
            return [0.0] * dim

        words = re.findall(r'\w+', text.lower())
        vec = np.zeros(dim, dtype=np.float32)

        for word in words:
            # Word token feature hash
            idx = (hash(word) ^ 0x55555555) % dim
            vec[idx] += 1.0

            # Subword n-grams (3 to 5 chars) for subword lexical matching
            if len(word) >= 3:
                for n in range(3, min(6, len(word) + 1)):
                    for i in range(len(word) - n + 1):
                        gram = word[i:i + n]
                        gram_idx = (hash(gram) ^ 0xAAAAAAAA) % dim
                        vec[gram_idx] += 0.35

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()
