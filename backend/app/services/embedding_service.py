"""Embedding service with a zero-dependency fallback.

``sentence-transformers`` is used when installed (set EMBEDDINGS_BACKEND=auto).
Otherwise a deterministic hashed bag-of-words + character n-gram embedding is
used, so compatibility scoring works offline and in tests without a model
download. Both paths return L2-normalised float32 vectors.
"""
from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

import numpy as np

from ..config import settings

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#.]*")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "with", "on", "at", "by",
    "is", "are", "was", "were", "be", "been", "this", "that", "as", "from", "will",
    "you", "we", "our", "your", "their", "it", "its", "can", "have", "has", "had",
    "using", "use", "used", "work", "working", "role", "job", "team", "candidate",
    "experience", "skills", "requirements", "responsibilities", "preferred", "required",
}

DIM = 512


def _tokens(text: str) -> list[str]:
    words = [w for w in _TOKEN_RE.findall((text or "").lower()) if len(w) > 1]
    words = [w for w in words if w not in _STOPWORDS]
    grams: list[str] = []
    for w in words:
        grams.append(w)
        padded = f"#{w}#"
        for n in (3, 4):
            grams.extend(padded[i : i + n] for i in range(max(0, len(padded) - n + 1)))
    return grams


def _hash(token: str) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def _hashed_embed(text: str) -> np.ndarray:
    vec = np.zeros(DIM, dtype=np.float32)
    for token in _tokens(text):
        h = _hash(token)
        idx = h % DIM
        sign = 1.0 if (h >> 63) & 1 else -1.0
        vec[idx] += sign
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


class EmbeddingService:
    def __init__(self) -> None:
        self.backend = "hashed"
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        if settings.embeddings_backend == "hashed":
            return
        try:  # optional heavy dependency
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._model = SentenceTransformer(settings.sentence_transformer_model)
            self.backend = "sentence-transformers"
        except Exception:
            self._model = None
            self.backend = "hashed"

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, DIM), dtype=np.float32)
        if self._model is not None:
            vectors = self._model.encode(
                texts, normalize_embeddings=True, show_progress_bar=False
            )
            return np.asarray(vectors, dtype=np.float32)
        return np.vstack([_hashed_embed(t) for t in texts])

    def similarity(self, a: str, b: str) -> float:
        if not a.strip() or not b.strip():
            return 0.0
        vecs = self.encode([a, b])
        return float(np.clip(np.dot(vecs[0], vecs[1]), 0.0, 1.0))

    def similarities(self, query: str, docs: list[str]) -> list[float]:
        if not docs:
            return []
        vecs = self.encode([query] + docs)
        sims = vecs[1:] @ vecs[0]
        return [float(np.clip(s, 0.0, 1.0)) for s in sims]

    @property
    def name(self) -> str:
        return self.backend


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, 0.0, 1.0))


def token_overlap(answer: str, points: list[str]) -> float:
    """Fraction of expected key phrases that appear in the answer."""
    if not points:
        return 0.0
    answer_l = answer.lower()
    hits = 0
    for point in points:
        keywords = [w for w in _TOKEN_RE.findall(point.lower()) if w not in _STOPWORDS and len(w) > 2]
        if not keywords:
            continue
        matched = sum(1 for k in keywords if k in answer_l)
        if matched / len(keywords) >= 0.4:
            hits += 1
    return hits / len(points)
