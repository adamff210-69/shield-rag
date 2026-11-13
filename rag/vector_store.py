"""
Vector Store and Document Retrieval Engine.
Handles document ingestion, text chunking, embedding index management, and similarity search.
"""

import uuid
import numpy as np
from typing import List, Dict, Any, Optional
from rag.embeddings import RAGEmbeddingEngine


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> List[str]:
    """Recursively split text into coherent semantic passages of max ~chunk_size with overlap."""
    if not text or len(text) <= chunk_size:
        return [text] if text else []

    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for para in paragraphs:
        para_stripped = para.strip()
        if not para_stripped:
            continue

        if current_length + len(para_stripped) <= chunk_size:
            current_chunk.append(para_stripped)
            current_length += len(para_stripped) + 2
        else:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
            
            if len(para_stripped) > chunk_size:
                lines = para_stripped.split("\n")
                sub_chunk = []
                sub_len = 0
                for line in lines:
                    if sub_len + len(line) <= chunk_size:
                        sub_chunk.append(line)
                        sub_len += len(line) + 1
                    else:
                        if sub_chunk:
                            chunks.append("\n".join(sub_chunk))
                        if len(line) > chunk_size:
                            for i in range(0, len(line), chunk_size - chunk_overlap):
                                chunks.append(line[i:i + chunk_size])
                            sub_chunk = []
                            sub_len = 0
                        else:
                            sub_chunk = [line]
                            sub_len = len(line)
                if sub_chunk:
                    chunks.append("\n".join(sub_chunk))
                current_chunk = []
                current_length = 0
            else:
                current_chunk = [para_stripped]
                current_length = len(para_stripped)

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return [c for c in chunks if c.strip()]


class DocumentChunk:
    """Dataclass representing a chunked document in the vector store."""
    def __init__(self, content: str, metadata: Optional[Dict[str, Any]] = None, chunk_id: Optional[str] = None):
        self.chunk_id = chunk_id or str(uuid.uuid4())[:8]
        self.page_content = content
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "page_content": self.page_content,
            "metadata": self.metadata
        }


class RAGVectorStore:
    """In-memory Vector Database for RAG storage and retrieval."""

    def __init__(self, embedding_engine: Optional[RAGEmbeddingEngine] = None):
        self.embedding_engine = embedding_engine or RAGEmbeddingEngine()
        self.chunks: List[DocumentChunk] = []
        self.embeddings_matrix: Optional[np.ndarray] = None
        self._load_default_knowledge_base()

    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None, auto_chunk: bool = True) -> List[str]:
        """Add raw texts to the vector store with automatic text chunking and embeddings."""
        if not texts:
            return []

        new_chunks = []
        for idx, text in enumerate(texts):
            base_meta = metadatas[idx] if metadatas and idx < len(metadatas) else {"source": "user_upload"}

            if auto_chunk and len(text) > 800:
                passages = chunk_text(text, chunk_size=800, chunk_overlap=100)
                for chunk_idx, passage in enumerate(passages):
                    chunk_meta = dict(base_meta)
                    chunk_meta["chunk_index"] = chunk_idx
                    chunk_meta["total_chunks"] = len(passages)
                    new_chunks.append(DocumentChunk(content=passage, metadata=chunk_meta))
            else:
                new_chunks.append(DocumentChunk(content=text, metadata=base_meta))

        # Compute embeddings for new texts
        new_embeddings = self.embedding_engine.embed_documents([c.page_content for c in new_chunks])
        new_matrix = np.array(new_embeddings, dtype=np.float32)

        self.chunks.extend(new_chunks)

        if self.embeddings_matrix is None:
            self.embeddings_matrix = new_matrix
        else:
            self.embeddings_matrix = np.vstack([self.embeddings_matrix, new_matrix])

        return [c.chunk_id for c in new_chunks]

    def similarity_search(
        self, 
        query: str, 
        top_k: int = 3, 
        min_score: float = 0.25,
        single_source_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Perform Hybrid cosine similarity & keyword search for a query string with optional Single Source filtering."""
        if not self.chunks or self.embeddings_matrix is None:
            return []

        import re
        query_vector = np.array(self.embedding_engine.embed_query(query), dtype=np.float32)

        # 1. Dense Cosine Similarity
        norm_matrix = self.embeddings_matrix / (np.linalg.norm(self.embeddings_matrix, axis=1, keepdims=True) + 1e-8)
        norm_query = query_vector / (np.linalg.norm(query_vector) + 1e-8)
        dense_scores = np.dot(norm_matrix, norm_query)

        # 2. Lexical Keyword Overlap Score
        stop_words = {"what", "is", "are", "the", "a", "an", "and", "or", "to", "in", "of", "for", "with", "how", "does", "do", "you", "your", "my", "about"}
        q_tokens = [w for w in re.findall(r'\w+', query.lower()) if w not in stop_words and len(w) >= 2]
        q_token_set = set(q_tokens)

        hybrid_scores = np.zeros(len(self.chunks), dtype=np.float32)

        for idx, chunk in enumerate(self.chunks):
            d_score = float(dense_scores[idx])
            c_text_lower = chunk.page_content.lower()

            kw_match_count = 0
            if q_token_set:
                for token in q_token_set:
                    if token in c_text_lower:
                        kw_match_count += 1
                kw_ratio = kw_match_count / len(q_token_set)
            else:
                kw_ratio = 0.0

            # Hybrid score combination
            h_score = (0.70 * d_score) + (0.30 * kw_ratio)
            if kw_ratio >= 0.8:
                h_score = max(h_score, d_score + 0.15)

            hybrid_scores[idx] = h_score

        # Sort indices by highest hybrid score
        top_k_indices = np.argsort(hybrid_scores)[::-1]

        results = []
        target_source = None
        
        # Adaptive thresholding: if max score is lower than min_score but > 0.15, allow top candidate
        effective_min = min_score
        if len(top_k_indices) > 0 and float(hybrid_scores[top_k_indices[0]]) < min_score:
            top_best = float(hybrid_scores[top_k_indices[0]])
            if top_best >= 0.12:
                effective_min = top_best - 0.05

        for idx in top_k_indices:
            score = float(hybrid_scores[idx])
            if score < effective_min:
                break

            chunk = self.chunks[idx]
            source = chunk.metadata.get("source", "")

            # Single Source Mode: enforce all retrieved chunks match the top-scoring chunk's source file
            if single_source_only:
                if target_source is None:
                    target_source = source
                elif source != target_source:
                    continue

            if len(results) >= top_k:
                break

            results.append({
                "chunk_id": chunk.chunk_id,
                "page_content": chunk.page_content,
                "metadata": chunk.metadata,
                "similarity_score": round(score, 4)
            })

        return results

    def clear(self):
        """Remove all chunks and reset the embeddings matrix."""
        self.chunks = []
        self.embeddings_matrix = None

    def delete_document_by_source(self, source: str) -> int:
        """Remove all chunks belonging to a specific source document."""
        initial_count = len(self.chunks)
        keep_indices = [i for i, c in enumerate(self.chunks) if c.metadata.get("source") != source]
        self.chunks = [self.chunks[i] for i in keep_indices]
        if self.embeddings_matrix is not None:
            if keep_indices:
                self.embeddings_matrix = self.embeddings_matrix[keep_indices]
            else:
                self.embeddings_matrix = None
        return initial_count - len(self.chunks)

    def _load_default_knowledge_base(self):
        """Pre-load knowledge base documents from disk if any files exist in knowledge_base directory."""
        import os

        kb_dir = "knowledge_base"
        if not os.path.exists(kb_dir):
            return

        texts = []
        metadatas = []

        for root, _, files in os.walk(kb_dir):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if content.strip():
                        texts.append(content)
                        f_lower = file.lower()
                        is_inj = (
                            "injected" in root.lower() or 
                            "malicious" in f_lower or 
                            "inject" in f_lower or 
                            "bipia" in f_lower or 
                            "secrag" in f_lower or 
                            "lakera" in f_lower or 
                            "canary" in f_lower or
                            "leak" in f_lower
                        )
                        topic = "General"
                        if "langgraph" in f_lower:
                            topic = "LangGraph Architecture"
                        elif "groq" in f_lower:
                            topic = "Groq LPU Hardware"
                        elif "financial" in f_lower or "secrag" in f_lower:
                            topic = "Corporate Finance"
                        elif "cybersecurity" in f_lower or "canary" in f_lower:
                            topic = "Cybersecurity"

                        metadatas.append({
                            "source": file,
                            "topic": topic,
                            "doc_type": "INJECTED" if is_inj else "BENIGN",
                            "citation": "Local Knowledge Base",
                            "filepath": filepath
                        })
                except Exception:
                    pass

        if texts:
            self.add_texts(texts, metadatas)

